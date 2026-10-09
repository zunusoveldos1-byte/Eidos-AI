"""All blocking voice operations live in this QObject's QThread."""

from pathlib import Path
from threading import Event
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from eidos.core.commands import CommandHandler
from eidos.core.config import AppConfig
from .recorder import Recorder, list_microphones
from .stt import WhisperSTT
from .tts import EdgeTTS


class VoiceWorker(QObject):
    progress = pyqtSignal(str, str)
    transcript = pyqtSignal(str)
    reply = pyqtSignal(str)
    audio = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()
    devices = pyqtSignal(object)
    devices_error = pyqtSignal(str)
    agent_progress = pyqtSignal(str, str)
    level = pyqtSignal(float)

    def __init__(self, recorder: Any = None, stt: Any = None, tts: Any = None) -> None:
        super().__init__()
        self.recorder = recorder or Recorder()
        if hasattr(self.recorder, 'level_callback'):
            self.recorder.level_callback = self.level.emit
        self.stt = stt or WhisperSTT()
        self.tts = tts or EdgeTTS()
        self.commands = CommandHandler()
        self.stop_event = Event()
        self.cancel_event = Event()

    @pyqtSlot()
    def refresh_devices(self) -> None:
        try:
            self.devices.emit(list_microphones())
        except Exception:
            self.devices_error.emit('Микрофоны недоступны. Установите голосовые зависимости и проверьте устройства Windows.')

    @pyqtSlot(object, object)
    def run_cycle(self, config: AppConfig, cache: Path) -> None:
        stage = 'recording'
        path: Path | None = None
        try:
            if self.cancel_event.is_set():
                return
            audio = self.recorder.record(config.microphone, self.stop_event, self.cancel_event,
                                         lambda: self.progress.emit('recording', 'Запись… Говорите команду и нажмите «Остановить».'))
            if audio is None or self.cancel_event.is_set():
                return
            stage = 'stt'
            text = self.stt.transcribe(audio, config, cache, self.progress.emit, self.cancel_event)
            del audio
            if self.cancel_event.is_set():
                return
            self.transcript.emit(text)
            stage = 'agent'
            answer = self.commands.handle(text)
            self.reply.emit(answer)
            if config.speak and text and not self.cancel_event.is_set():
                stage = 'tts'
                self.progress.emit('synthesizing', 'Синтез речи онлайн…')
                path = self.tts.synthesize(answer, config.tts_voice, self.cancel_event)
                if path and not self.cancel_event.is_set():
                    self.audio.emit(path)
                    path = None  # Ownership passes to the GUI player.
        except Exception as exc:
            if not self.cancel_event.is_set():
                if isinstance(exc, ValueError) and stage == 'stt':
                    message = str(exc)
                elif stage == 'agent' and isinstance(exc, (ValueError, PermissionError, TimeoutError, ConnectionError, RuntimeError)):
                    from eidos.agent.memory import redact_secrets
                    message = redact_secrets(str(exc))[:1000]
                else:
                    message = {
                        'recording': 'Не удалось открыть или записать микрофон. Проверьте устройство и разрешения Windows.',
                        'stt': 'Не удалось загрузить модель или распознать речь. Для первой загрузки нужен интернет; проверьте настройки CPU/CUDA.',
                        'agent': 'Не удалось обработать команду. Проверьте модель / подключение в разделе «Ассистент».',
                        'tts': 'Не удалось озвучить ответ. Проверьте интернет. Текст ответа доступен выше.',
                    }[stage]
                self.error.emit(message)
        finally:
            if path:
                path.unlink(missing_ok=True)
            self.finished.emit()
