"""Native Qt PCM output from QBuffer; no media decoder or audio files."""
from PyQt6.QtCore import QObject, QTimer, QBuffer, QByteArray, QIODevice, pyqtSignal
from .pcm import PCMAudio


class AudioPlayback(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    level = pyqtSignal(float)
    pause_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output = self._buffer = self._audio = None
        self.volume = .8
        self.paused = False
        self.has_audio_levels = True
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(80)
        self._level_timer.timeout.connect(self._measure_level)

    @property
    def active(self):
        return self._audio is not None

    def set_volume(self, percent):
        self.volume = max(0, min(100, percent)) / 100
        if self._output is not None:
            self._output.setVolume(self.volume)

    def play(self, audio):
        self.stop()
        if not isinstance(audio, PCMAudio) or not audio.data:
            self.error.emit('Озвучка не содержит PCM-аудио.')
            return
        try:
            from PyQt6.QtMultimedia import QAudioSink, QAudioFormat, QMediaDevices
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                raise OSError('No output device')
            fmt = QAudioFormat()
            fmt.setSampleRate(audio.sample_rate)
            fmt.setChannelCount(audio.channels)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            self._audio = audio
            self._buffer = QBuffer(self)
            self._buffer.setData(QByteArray(audio.data))
            self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)  # RAM-backed QIODevice
            self._output = QAudioSink(device, fmt, self)
            self._output.setVolume(self.volume)
            self._output.stateChanged.connect(self._state_changed)
            self._output.start(self._buffer)
            if self.active:
                self._level_timer.start()
        except Exception:
            self.stop()
            self.error.emit('Не удалось воспроизвести PCM. Проверьте выходное устройство Windows.')

    def _state_changed(self, state):
        from PyQt6.QtMultimedia import QAudio
        if not self.active:
            return
        if state == QAudio.State.IdleState:
            self.stop()
            self.finished.emit()
        elif state == QAudio.State.StoppedState and self._output.error() != QAudio.Error.NoError:
            self.stop()
            self.error.emit('Не удалось воспроизвести PCM. Проверьте выходное устройство Windows.')

    def _measure_level(self):
        if not self.active or self.paused:
            self.level.emit(0.)
            return
        import numpy as np
        offset = int(self._output.processedUSecs() * self._audio.sample_rate / 1000000) * self._audio.channels * 2
        data = self._audio.data[offset:offset + 2048]
        samples = np.frombuffer(data, dtype='<i2').astype(np.float32) / 32768.
        self.level.emit(float(np.sqrt(np.mean(samples ** 2))) * self.volume if samples.size else 0.)

    def pause(self):
        if self.active and not self.paused:
            self.paused = True
            self._output.suspend()
            self.level.emit(0.)
            self.pause_changed.emit(True)

    def resume(self):
        if self.active and self.paused:
            self.paused = False
            self._output.resume()
            self.pause_changed.emit(False)

    def stop(self):
        self._audio = None
        self.paused = False
        self._level_timer.stop()
        self.level.emit(0.)
        output, self._output = self._output, None
        buffer, self._buffer = self._buffer, None
        if output is not None:
            output.stop()
            output.deleteLater()
        if buffer is not None:
            buffer.close()
            buffer.deleteLater()

    def dispose(self):
        self.stop()
