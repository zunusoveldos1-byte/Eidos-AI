"""QObject worker with cooperative cancellation and GUI approval bridge."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import time
from enum import Enum

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from .hardware import diagnose, ollama_rss_mib
from .harness import TaskContext, Harness
from .providers import provider_for, pull_model, start_ollama, request_json
from .tools import build_registry


class TaskState(str, Enum):
    READY = 'ready'
    THINKING = 'thinking'
    ACTING = 'acting'
    CHECKING = 'checking'
    CONFIRMING = 'confirming'
    CANCELLING = 'cancelling'
    CANCELLED = 'cancelled'
    ERROR = 'error'
    CLOSING = 'closing'


@dataclass
class Approval:
    action: str
    event: threading.Event = field(default_factory=threading.Event)
    accepted: bool = False


class AgentWorker(QObject):
    progress = pyqtSignal(str, str)
    answer = pyqtSignal(str)
    data = pyqtSignal(str, object)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    confirmation = pyqtSignal(object)

    def __init__(self, service):
        super().__init__()
        self.service = service

    def confirm(self, action, context):
        approval = Approval(action)
        self.confirmation.emit(approval)
        while not approval.event.wait(.1):
            context.check()
        context.check()
        return approval.accepted

    @pyqtSlot(object)
    def perform(self, task):
        kind, payload, context = task
        context.confirm = lambda action: self.confirm(action, context)
        context.progress = self.progress.emit
        try:
            context.check()
            if kind == 'chat':
                self.answer.emit(self.service.respond(payload, context))
            elif kind == 'remote':
                self.data.emit(kind, self.service.respond_remote(payload, context))
            elif kind == 'receive':
                self.data.emit(kind, self.service.receive(context))
            elif kind == 'memory_save':
                if not self.service.settings.memory_enabled:
                    raise ValueError('Постоянная память выключена')
                if payload['id'] is not None:
                    self.service.memory.edit(payload['id'], payload['content'], payload['source'])
                elif self.service.memory.add(payload['kind'], payload['content'], payload['source']) is None:
                    raise ValueError('Запись содержит возможный секрет')
                self.data.emit(kind, 'Запись памяти сохранена.')
            elif kind == 'memory_delete':
                self.service.memory.delete(payload)
                self.service.history.clear()
                self.data.emit(kind, 'Запись памяти удалена.')
            elif kind == 'memory_clear':
                self.service.memory.clear(payload)
                self.service.history.clear()
                self.data.emit(kind, 'Память очищена.')
            elif kind == 'tool':
                registry = build_registry(self.service.settings, self.service.memory)
                self.data.emit(kind, registry.execute(payload[0], payload[1], context).text)
            elif kind == 'hardware':
                self.progress.emit('thinking', 'Диагностика оборудования…')
                self.data.emit(kind, diagnose())
            elif kind == 'start':
                self.data.emit(kind, start_ollama(Path(__file__).parents[2]))
            elif kind == 'pull':
                self.data.emit(kind, pull_model(self.service.settings, context))
            elif kind == 'model_test':
                import psutil
                provider = provider_for(self.service.settings, self.service.secrets)
                started = time.monotonic()
                answer = provider.chat([{'role': 'user', 'content': 'Поздоровайся на русском одной короткой фразой.'}], [], context)
                registry = build_registry(self.service.settings, self.service.memory)
                schema = registry.tools['calendar_list'].schema()
                calls = provider.chat([{'role': 'system', 'content': 'Используй calendar_list для просмотра календаря.'},
                                       {'role': 'user', 'content': 'Покажи мой календарь, вызови инструмент.'}], [schema], context)
                requested = calls.get('tool_calls', [])
                valid = bool(requested)
                for call in requested:
                    fn = call['function']
                    if fn['name'] != 'calendar_list':
                        valid = False
                        break
                    args = fn['arguments']
                    registry.execute(fn['name'], json.loads(args) if isinstance(args, str) else args, context)
                stats = {'answer': answer['content'], 'tool_call_verified': valid, 'seconds_two_calls': round(time.monotonic()-started, 2),
                         'ollama_rss_mib': ollama_rss_mib(), 'ram_available_gib': round(psutil.virtual_memory().available / 2**30, 2),
                         'last_generation': getattr(provider, 'metrics', {})}
                if self.service.settings.provider == 'ollama':
                    stats['running_models'] = request_json('GET', self.service.settings.ollama_url + '/api/ps', context=context)
                self.service.model_connected = valid
                self.data.emit(kind, stats)
            elif kind == 'search_test':
                from dataclasses import replace
                registry = build_registry(replace(self.service.settings, search_provider='brave'), self.service.memory)
                result = registry.execute('web_search', {'query':'Python official documentation'}, context)
                self.data.emit(kind, result.text)
            elif kind.startswith('test_'):
                self.data.emit(kind, self.service.bot(kind[5:]).test(context))
            else:
                raise ValueError('Неизвестная операция')
        except InterruptedError:
            self.error.emit('Задача отменена. Уже выполненные действия не откатываются.')
        except Exception as exc:
            # Never serialize transport exceptions (some include secret-bearing URLs).
            safe = str(exc) if isinstance(exc, (ValueError, PermissionError, TimeoutError, ConnectionError, RuntimeError)) else 'Операция не выполнена. Проверьте входные данные / доступ к сервису.'
            from .memory import has_secret
            self.error.emit('Ошибка операции.' if has_secret(safe, context.secret_values) else safe[:1000])
        finally:
            self.finished.emit()


class AgentController(QObject):
    requested = pyqtSignal(object)
    progress = pyqtSignal(str, str)
    answer = pyqtSignal(str)
    data = pyqtSignal(str, object)
    error = pyqtSignal(str)
    confirmation = pyqtSignal(object)
    finished = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.thread = QThread(self)
        self.worker = AgentWorker(service)
        self.worker.moveToThread(self.thread)
        self.requested.connect(self.worker.perform)
        self.worker.progress.connect(self._progress)
        self.worker.answer.connect(self.answer)
        self.worker.data.connect(self.data)
        self.worker.error.connect(self._error)
        self.worker.confirmation.connect(self.confirmation)
        self.worker.finished.connect(self._finished)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.closed)
        self.active = False
        self.closing = False
        self.state = TaskState.READY
        self.context = None
        self.thread.start()

    def start(self, kind, payload=None, *, incognito=False):
        if self.active or self.closing:
            return False
        self.context = self.service.context(timeout=7200 if kind == 'pull' else 180 if kind == 'model_test' else 120,
                                            incognito=incognito)
        self.active = True
        self.state = TaskState.THINKING
        self.progress.emit('thinking', 'Начало операции…')
        self.requested.emit((kind, payload, self.context))
        return True

    def cancel(self):
        if self.context:
            self.state = TaskState.CANCELLING
            self.context.cancel.set()

    @pyqtSlot(str, str)
    def _progress(self, state, text):
        if self.closing or (self.context and self.context.cancel.is_set()):
            return
        self.state = TaskState(state)
        self.progress.emit(state, text)

    @pyqtSlot(str)
    def _error(self, message):
        self.state = TaskState.CANCELLED if self.context and self.context.cancel.is_set() else TaskState.ERROR
        self.error.emit(message)

    @pyqtSlot()
    def _finished(self):
        self.active = False
        if self.state not in (TaskState.ERROR, TaskState.CANCELLED, TaskState.CLOSING):
            self.state = TaskState.READY
        self.finished.emit()

    def shutdown(self):
        self.closing = True
        self.cancel()
        self.state = TaskState.CLOSING
        self.thread.quit()
