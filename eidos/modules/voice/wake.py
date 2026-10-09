"""Optional local wake detection; the stream belongs exclusively to its worker."""

from array import array
from copy import copy
from pathlib import Path
from threading import Event
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal


class _WakeThread(QThread):
    detected = pyqtSignal()
    level = pyqtSignal(float)
    status = pyqtSignal(str)
    failed = pyqtSignal()

    def __init__(self, config, key, parent):
        super().__init__(parent)
        self.config, self.key = config, key
        self.cancel = Event()

    def run(self) -> None:
        engine = stream = None
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
            stream = sd.RawInputStream(device=self.config.microphone, channels=1,
                                       samplerate=engine.sample_rate, blocksize=engine.frame_length,
                                       dtype='int16')
            stream.start()
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
                if engine.process(samples) >= 0:
                    self.detected.emit()
                    break
        except Exception as exc:
            if not self.cancel.is_set():
                message = str(exc).replace(self.key, '[ключ скрыт]')
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


class WakeController(QObject):
    activated = pyqtSignal()
    level = pyqtSignal(float)
    status = pyqtSignal(str)
    stopped = pyqtSignal()

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
        self._restart = QTimer(self)
        self._restart.setSingleShot(True)
        self._restart.setInterval(400)
        self._restart.timeout.connect(self._start)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def configure(self, config) -> None:
        if self._closed:
            return
        try:
            key = self.secrets.get('porcupine_access_key')
        except Exception:
            key = None
        relevant = ('wake_word_enabled', 'wake_keyword_path', 'wake_model_path',
                    'microphone', 'wake_sensitivity')
        if (self._config is not None and not self._failed and key == self._key and
                all(getattr(config, name, None) == getattr(self._config, name, None)
                    for name in relevant)):
            return
        self._config = copy(config)
        self._failed = False
        self._restart.stop()
        self._stop()
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
        thread.level.connect(self.level)
        thread.status.connect(self.status)
        thread.failed.connect(self._failure)
        thread.finished.connect(self._finished)
        thread.start()

    def _stop(self) -> None:
        if self._thread is not None:
            self._thread.cancel.set()

    def _detected(self) -> None:
        if not self._wanted() or (self._thread and self._thread.cancel.is_set()):
            return
        self._busy = True
        self._stop()
        self.activated.emit()

    def _failure(self) -> None:
        if self._thread and self._thread.cancel.is_set():
            return
        self._failed = True
        self._restart.stop()

    def _finished(self) -> None:
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
