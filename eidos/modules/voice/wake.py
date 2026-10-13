"""Optional local wake detection; the stream belongs exclusively to its worker."""

from array import array
from copy import copy
from pathlib import Path
from threading import Event
from collections import deque
from uuid import uuid4
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal


class RingCapture:
    """1.5 s pre-roll followed by the command, from the same microphone stream."""
    def __init__(self, sample_rate, sensitivity=.5, max_seconds=30):
        self.sample_rate = sample_rate
        self.limit = int(sample_rate * max_seconds)
        self.threshold = .012 * (1.8 - 1.4 * sensitivity)
        self._ring = deque()
        self._count = 0
        self._chunks = []
        self.triggered = self.done = False
        self._post = self._silence = 0
        self._noise = .002

    @property
    def buffered_samples(self):
        return self._count

    def feed(self, samples, detected=False):
        import numpy as np
        if self.done:
            return
        frame = np.asarray(samples, dtype=np.float32).copy()
        if not self.triggered:
            self._ring.append(frame)
            self._count += frame.size
            while self._ring and self._count > int(self.sample_rate * 1.5):
                extra = self._count - int(self.sample_rate * 1.5)
                head = self._ring.popleft()
                removed = min(extra, head.size)
                self._count -= removed
                if removed < head.size:
                    self._ring.appendleft(head[removed:])
            if detected:
                self.triggered = True
                self._chunks = list(self._ring)
                self._ring.clear()
            else:
                rms = float(np.sqrt(np.mean(frame ** 2)))
                if rms < self.threshold:
                    self._noise = .97 * self._noise + .03 * rms
            return
        remaining = self.limit - self._count
        self._chunks.append(frame[:remaining])
        self._count += min(frame.size, remaining)
        self._post += frame.size
        rms = float(np.sqrt(np.mean(frame ** 2)))
        threshold = max(self.threshold, self._noise * 2.2)
        self._silence = self._silence + frame.size if rms < threshold else 0
        # Give a user who pauses after the name time to start the command.
        self.done = self._count >= self.limit or (self._post >= self.sample_rate and
                                                  self._silence >= self.sample_rate * .9)

    def audio(self):
        import numpy as np
        return np.concatenate(self._chunks) if self._chunks else np.array([], dtype=np.float32)


class _WakeThread(QThread):
    detected = pyqtSignal()
    captured = pyqtSignal(object, str)
    level = pyqtSignal(float)
    status = pyqtSignal(str)
    failed = pyqtSignal()
    microphone_changed = pyqtSignal(str, str)

    def __init__(self, config, key, parent):
        super().__init__(parent)
        self.config, self.key = config, key
        self.cancel = Event()
        self.submit = Event()

    def run(self) -> None:
        engine = stream = None
        opening_microphone = microphone_failed = False
        try:
            try:
                import pvporcupine
            except ImportError as exc:
                raise RuntimeError('Установите pvporcupine для локального слова активации.') from exc
            import sounddevice as sd
            engine = pvporcupine.create(
                access_key=self.key, keyword_paths=[self.config.wake_keyword_path],
                model_path=self.config.wake_model_path,
                sensitivities=[max(0., min(1., self.config.wake_sensitivity))])
            if self.cancel.is_set():
                return
            opening_microphone = True
            stream = sd.RawInputStream(device=self.config.microphone, channels=1,
                                       samplerate=engine.sample_rate, blocksize=engine.frame_length,
                                       dtype='int16')
            stream.start()
            self.microphone_changed.emit('waiting', '')
            capture = RingCapture(engine.sample_rate,
                                  getattr(self.config, 'voice_sensitivity', .5),
                                  getattr(self.config, 'voice_max_seconds', 30))
            self.status.emit('Ожидаю слово активации…')
            next_level = 0.
            while not self.cancel.is_set():
                pcm, overflow = stream.read(engine.frame_length)
                if overflow:
                    raise OSError('Потеря аудиоданных при ожидании слова активации.')
                if self.cancel.is_set():
                    break
                samples = array('h', pcm)
                now = time.monotonic()
                if now >= next_level:
                    self.level.emit(min(1., (sum(value * value for value in samples) /
                                             max(1, len(samples))) ** .5 / 32768))
                    next_level = now + .1
                import numpy as np
                found = not capture.triggered and engine.process(samples) >= 0
                capture.feed(np.asarray(samples, dtype=np.float32) / 32768., found)
                if found:
                    self.microphone_changed.emit('recording', '')
                    self.detected.emit()
                    self.status.emit('Слушаю команду после «Эйдос»…')
                if capture.done or (capture.triggered and self.submit.is_set()):
                    from .recorder import resample
                    self.captured.emit(resample(capture.audio(), engine.sample_rate), uuid4().hex)
                    break
        except Exception as exc:
            if not self.cancel.is_set():
                message = str(exc).replace(self.key, '[ключ скрыт]')
                if opening_microphone:
                    microphone_failed = True
                    self.microphone_changed.emit('error', 'Ошибка микрофона: проверьте подключение и разрешения Windows. ' + message[:300])
                self.status.emit(f'Слово активации недоступно: {message}')
                self.failed.emit()
        finally:
            try:
                if stream is not None:
                    try:
                        stream.abort()
                    finally:
                        stream.close()
            finally:
                if engine is not None:
                    engine.delete()
                if not microphone_failed:
                    self.microphone_changed.emit('inactive', '')


class WakeController(QObject):
    activated = pyqtSignal()
    command_ready = pyqtSignal(object, str)
    level = pyqtSignal(float)
    status = pyqtSignal(str)
    stopped = pyqtSignal()
    microphone_changed = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None, secrets) -> None:
        super().__init__(parent)
        self.secrets = secrets
        self._config = None
        self._thread = None
        self._paused = False
        self._busy = False
        self._closed = False
        self._failed = False
        self._key = None
        self._capturing = False
        self.microphone_state = 'inactive'
        self._restart = QTimer(self)
        self._restart.setSingleShot(True)
        self._restart.setInterval(400)
        self._restart.timeout.connect(self._start)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    @property
    def capturing(self):
        return self._capturing and self.is_running

    def finish_command(self):
        if self.capturing:
            self._thread.submit.set()

    def configure(self, config) -> None:
        if self._closed:
            return
        key = None
        if config.wake_word_enabled:
            try:
                key = self.secrets.get('porcupine_access_key')
            except Exception:
                pass
        relevant = ('wake_word_enabled', 'wake_keyword_path', 'wake_model_path',
                    'microphone', 'wake_sensitivity', 'voice_sensitivity', 'voice_max_seconds')
        if (self._config is not None and not self._failed and key == self._key and
                all(getattr(config, name, None) == getattr(self._config, name, None)
                    for name in relevant)):
            return
        self._config = copy(config)
        self._failed = False
        self._restart.stop()
        self._stop()
        self._microphone_changed('inactive', '')
        if not config.wake_word_enabled:
            self.status.emit('Слово активации отключено')
            return
        self._key = key
        if not self._key:
            self._failed = True
            self.status.emit('Для слова активации укажите Porcupine AccessKey в настройках.')
            return
        for name, suffix, label in [('wake_keyword_path', '.ppn', 'модель слова .ppn для Windows'),
                                     ('wake_model_path', '.pv', 'языковая модель .pv')]:
            path = Path(getattr(config, name, ''))
            if path.suffix.lower() != suffix or not path.is_file():
                self._failed = True
                self.status.emit(f'Для слова активации нужна {label}: проверьте путь.')
                return
        if self._thread is None:
            self._start()

    def _wanted(self) -> bool:
        return bool(self._config and self._config.wake_word_enabled and self._key and
                    not (self._paused or self._busy or self._closed or self._failed))

    def _start(self) -> None:
        if not self._wanted() or self._thread is not None:
            return
        thread = _WakeThread(self._config, self._key, self)
        self._thread = thread
        thread.detected.connect(self._detected)
        thread.captured.connect(self._captured)
        thread.level.connect(self.level)
        thread.status.connect(self.status)
        thread.failed.connect(self._failure)
        thread.microphone_changed.connect(self._microphone_changed)
        thread.finished.connect(self._finished)
        thread.start()

    def _stop(self) -> None:
        if self._thread is not None:
            self._thread.cancel.set()
        if self.microphone_state != 'error':
            self._microphone_changed('inactive', '')

    def _microphone_changed(self, state, message):
        if state in ('waiting', 'recording') and (not self._wanted() or
                (self._thread and self._thread.cancel.is_set())):
            return
        self.microphone_state = state
        self.microphone_changed.emit(state, message)

    def _detected(self) -> None:
        if not self._wanted() or (self._thread and self._thread.cancel.is_set()):
            return
        self._capturing = True
        self.activated.emit()

    def _captured(self, audio, recording_id):
        if self._wanted() and self._capturing and not self._thread.cancel.is_set():
            self._capturing = False
            self._busy = True
            self.command_ready.emit(audio, recording_id)

    def _failure(self) -> None:
        if self._thread and self._thread.cancel.is_set():
            return
        self._failed = True
        self._restart.stop()

    def _finished(self) -> None:
        self._capturing = False
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.deleteLater()
        self.level.emit(0.)
        self.stopped.emit()
        if self._wanted():
            self._restart.start()

    def pause(self, paused: bool) -> None:
        if self._paused == paused:
            return
        self._paused = paused
        self._restart.stop()
        if paused:
            self._stop()
            self.status.emit('Прослушивание приостановлено')
        elif self._wanted():
            self._restart.start()

    def set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self._restart.stop()
        if busy:
            self._stop()
        elif self._wanted():
            self._restart.start()

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._restart.stop()
        self._stop()
