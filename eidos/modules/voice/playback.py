"""QtMultimedia playback and temporary file ownership, in the GUI thread."""

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal


class AudioPlayback(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._player = None
        self._output = None
        self._path: Path | None = None
        self._pending: set[Path] = set()
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setInterval(200)
        self._cleanup_timer.timeout.connect(self._retry_cleanup)
        self.volume = 0.8

    def set_volume(self, percent: int) -> None:
        self.volume = max(0, min(100, percent)) / 100
        if self._output is not None:
            self._output.setVolume(self.volume)

    @property
    def active(self) -> bool:
        return self._path is not None

    def play(self, path: Path) -> None:
        self.stop()
        self._path = path
        try:
            from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

            if self._player is None:
                self._output = QAudioOutput(self)
                self._output.setVolume(self.volume)
                self._player = QMediaPlayer(self)
                self._player.setAudioOutput(self._output)
                self._player.mediaStatusChanged.connect(self._media_status)
                self._player.errorOccurred.connect(self._media_error)
            self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
            self._player.play()
        except Exception:
            self.stop()
            self.error.emit('Не удалось запустить звук через QtMultimedia.')

    def _media_status(self, status: object) -> None:
        from PyQt6.QtMultimedia import QMediaPlayer

        if status == QMediaPlayer.MediaStatus.EndOfMedia and self.active:
            self.stop()
            self.finished.emit()

    def _media_error(self, error: object, message: str) -> None:
        if self.active:
            self.stop()
            self.error.emit('Не удалось воспроизвести звук. Проверьте выходное устройство Windows.')

    def stop(self) -> None:
        path, self._path = self._path, None
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
        if path:
            self._pending.add(path)
        self._retry_cleanup()

    def _retry_cleanup(self) -> None:
        for path in list(self._pending):
            try:
                path.unlink(missing_ok=True)
                self._pending.remove(path)
            except OSError:
                pass  # Windows may hold a decoder handle until the next event loop turn.
        if self._pending:
            self._cleanup_timer.start()
        else:
            self._cleanup_timer.stop()

    def dispose(self) -> None:
        self.stop()
        # Releasing the decoder before final cleanup avoids open handles on Windows.
        if self._player is not None:
            from PyQt6 import sip

            sip.delete(self._player)
            self._player = None
        self._retry_cleanup()
        if self._pending:
            logging.getLogger('eidos').warning('Не удалось удалить временный аудиофайл.')
