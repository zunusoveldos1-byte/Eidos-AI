"""Worker requests are handed to JonSnow only in the Qt GUI thread."""
from dataclasses import dataclass, field
from threading import Event
import time
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot


@dataclass
class UIRequest:
    action: str
    cancel: Event
    done: Event = field(default_factory=Event)
    answer: str = ''
    error: str = ''


class VoiceUIBridge(QObject):
    requested = pyqtSignal(object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.requested.connect(self._execute)

    def request(self, action, cancel):
        request = UIRequest(action, cancel)
        self.requested.emit(request)
        deadline = time.monotonic() + 10
        while not request.done.wait(.05):
            if cancel.is_set():
                return ''
            if time.monotonic() >= deadline:
                cancel.set()
                raise TimeoutError('Интерфейс не ответил на голосовую команду')
        if request.error:
            raise RuntimeError(request.error)
        return request.answer

    @pyqtSlot(object)
    def _execute(self, request):
        try:
            if not request.cancel.is_set() and not self.window._closing:
                request.answer = self.execute(request.action)
        except Exception as exc:
            request.error = str(exc)
        finally:
            request.done.set()

    def execute(self, action):
        translation = self.window.translation
        if action == 'translate_region':
            if translation.is_running or translation._selecting:
                return 'Выделение или перевод уже выполняется.'
            translation.start_capture()
            return 'Выделите фрагмент экрана. Escape отменяет выделение.'
        if action in ('read_original', 'read_translation'):
            panel = translation.original if action == 'read_original' else translation.translated
            text = panel.text.toPlainText().strip()
            return text or ('Сначала выделите область и дождитесь распознавания.' if action == 'read_original'
                            else 'Сначала выделите область и дождитесь перевода.')
        raise ValueError('Неизвестная команда интерфейса')
