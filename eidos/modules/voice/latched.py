"""Independent local input owner: Vosk continues while the answer is processed."""
from dataclasses import dataclass
from threading import Event
from time import perf_counter
from PyQt6.QtCore import QThread, pyqtSignal
from .recorder import Recorder
from .stt import LocalSTT
from .intents import RETRY_SPEECH


@dataclass(frozen=True)
class RecognizedSpeech:
    text: str
    latency_ms: float
    overlapped_output: bool = False


class LatchedInput(QThread):
    recognized = pyqtSignal(object)
    microphone_changed = pyqtSignal(str, str)
    level = pyqtSignal(float)
    speech_activity = pyqtSignal(float, bool)
    failed = pyqtSignal(str)

    def __init__(self, config, cache, parent=None, recorder=None, stt=None):
        super().__init__(parent)
        self.setObjectName('EidosLatchedInput')
        self.config, self.cache = config, cache
        self.cancel = Event()
        self.output_active = Event()
        self._overlap = False
        self.recorder = recorder or Recorder()
        self.stt = stt or LocalSTT()

    def stop(self):
        self.cancel.set()

    def _speech_started(self):
        self._overlap = self.output_active.is_set()
        self.microphone_changed.emit('recording', '')

    def run(self):
        try:
            self.recorder.configure(self.config)
            self.recorder.level_callback = self.level.emit
            self.recorder.activity_callback = self.speech_activity.emit
            self.recorder.speech_callback = self._speech_started
            engine = self.stt.select(self.config)
            while not self.cancel.is_set():
                self._overlap = False
                streaming = self.config.stt_engine == 'vosk'
                if streaming:
                    if not engine.begin_stream(self.config, self.cache, lambda *args: None, self.cancel):
                        break
                    self.recorder.chunk_callback = lambda chunk: engine.feed(chunk, self.cancel)
                else:
                    self.recorder.chunk_callback = None
                stop = Event()
                audio = self.recorder.record(self.config.microphone, stop, self.cancel,
                    lambda: self.microphone_changed.emit('enabled', ''))
                if audio is None or self.cancel.is_set(): break
                try:
                    text = (engine.finish_stream(self.cancel) if streaming else engine.transcribe(
                        audio, self.config, self.cache, lambda *args: None, self.cancel))
                except ValueError as exc:
                    if RETRY_SPEECH in str(exc):
                        continue  # Noise/uncertain input is not a reason to unlatch.
                    raise
                ended = self.recorder.speech_ended_at or perf_counter()
                self.recognized.emit(RecognizedSpeech(text, (perf_counter() - ended) * 1000, self._overlap))
                self.microphone_changed.emit('enabled', '')
        except Exception:
            if not self.cancel.is_set():
                self.failed.emit('Голосовой поток недоступен. Проверьте микрофон и локальную модель Vosk.')
        finally:
            self.recorder.chunk_callback = None
            self.recorder.close()
            self.microphone_changed.emit('inactive', '')
