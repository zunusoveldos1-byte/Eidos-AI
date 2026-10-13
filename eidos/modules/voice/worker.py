"""All blocking voice operations live in this QObject's QThread."""

from pathlib import Path
from threading import Event
from typing import Any
from collections import deque
from uuid import uuid4

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
    microphone_changed = pyqtSignal(str, str)

    def __init__(self, recorder: Any = None, stt: Any = None, tts: Any = None) -> None:
        super().__init__()
        self.recorder = recorder or Recorder()
        if hasattr(self.recorder, 'level_callback'):
            self.recorder.level_callback = self.level.emit
        if hasattr(self.recorder, 'speech_callback'):
            self.recorder.speech_callback = self._speech_started
        self._capture_started = self._speech_heard = False
        self.stt = stt or WhisperSTT()
        self.tts = tts or EdgeTTS()
        self.commands = CommandHandler()
        self.stop_event = Event()
        self.cancel_event = Event()
        self._recordings = deque(maxlen=128)
        self.current_config = AppConfig()
        self.full_reply = False

    @pyqtSlot()
    def refresh_devices(self) -> None:
        try:
            self.devices.emit(list_microphones())
        except Exception:
            self.devices_error.emit('Микрофоны недоступны. Установите голосовые зависимости и проверьте устройства Windows.')

    @pyqtSlot(object, object)
    def run_cycle(self, config: AppConfig, cache: Path) -> None:
        self._run(config, cache)

    @pyqtSlot(object, object, object, str, bool)
    def run_audio(self, config, cache, audio, recording_id, wake) -> None:
        self._run(config, cache, audio, recording_id, wake)

    def _speech_started(self):
        self._speech_heard = True
        if self._capture_started and not self.cancel_event.is_set():
            self.microphone_changed.emit('recording', '')

    def _microphone_started(self):
        # Recorder calls this only after InputStream.start() succeeds.
        self._capture_started = True
        if not self.cancel_event.is_set():
            self.microphone_changed.emit('enabled', '')
            if self._speech_heard:
                self.microphone_changed.emit('recording', '')
            self.progress.emit('recording', 'Слушаю · нажмите микрофон, чтобы отправить')

    def _run(self, config, cache, supplied_audio=None, recording_id=None, wake=False):
        self.current_config = config
        self.full_reply = False
        stage = 'recording'
        path: Path | None = None
        try:
            if self.cancel_event.is_set():
                return
            recording_id = recording_id or uuid4().hex
            if recording_id in self._recordings:
                return
            self._recordings.append(recording_id)
            if hasattr(self.recorder, 'configure'):
                self.recorder.configure(config)
            audio = supplied_audio
            if audio is None:
                self._capture_started = self._speech_heard = False
                try:
                    audio = self.recorder.record(config.microphone, self.stop_event, self.cancel_event,
                                                 self._microphone_started)
                finally:
                    self._capture_started = False
                    self.microphone_changed.emit('inactive', '')
            if audio is None or self.cancel_event.is_set():
                return
            stage = 'stt'
            text = self.stt.transcribe(audio, config, cache, self.progress.emit, self.cancel_event)
            del audio
            if self.cancel_event.is_set():
                return
            from .intents import strip_wake_prefix, RETRY_SPEECH
            if wake:
                command = strip_wake_prefix(text)
                if command == text.strip():
                    from .intents import ui_intent
                    from eidos.agent.harness import deterministic_call
                    # Porcupine can detect the name even when STT omits it. Only
                    # a complete explicit known command is safe in that case.
                    apps = getattr(getattr(self.commands, 'service', None), 'settings', None)
                    if not ui_intent(command) and not deterministic_call(command, getattr(apps, 'approved_apps', ())):
                        raise ValueError(RETRY_SPEECH)
                text = command
            if not text.strip():
                raise ValueError(RETRY_SPEECH)
            self.transcript.emit(text)
            stage = 'agent'
            answer = self.commands.handle(text)
            if self.cancel_event.is_set():
                return
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
                if stage == 'recording':
                    self.microphone_changed.emit('error', message)
                self.error.emit(message)
        finally:
            if path:
                path.unlink(missing_ok=True)
            self.finished.emit()
