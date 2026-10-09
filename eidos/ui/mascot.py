"""Transparent local mascot with four states and finite, optional animation."""
from functools import lru_cache
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, pyqtProperty
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QSizePolicy, QWidget
from .theme import ASSETS


@lru_cache(maxsize=1)
def frames() -> dict[str, QPixmap]:
    atlas = QPixmap(str(ASSETS / 'mascot-atlas.png'))
    width, height = atlas.width() // 2, atlas.height() // 2
    return {state: atlas.copy((index % 2) * width, (index // 2) * height, width, height)
            for index, state in enumerate(('ready', 'listening', 'thinking', 'error'))}


class Mascot(QWidget):
    def __init__(self, size: int = 180) -> None:
        super().__init__()
        self.state = 'ready'
        self.animations_enabled = True
        self._offset = 0.0
        self._size = size
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(size)
        self.setMinimumWidth(min(size, 80))
        self.setMaximumWidth(size + 40)
        self.animation = QPropertyAnimation(self, b'offset', self)
        self.animation.setDuration(800)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.setStartValue(0.0)
        self.animation.setKeyValueAt(0.5, -4.0)
        self.animation.setEndValue(0.0)
        self.setAccessibleName('Маскот Eidos: готов')

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    @pyqtProperty(float)
    def offset(self) -> float:
        return self._offset

    @offset.setter
    def offset(self, value: float) -> None:
        self._offset = value
        self.update()

    def set_animations(self, enabled: bool) -> None:
        self.animations_enabled = enabled
        if not enabled:
            self.animation.stop()
            self.offset = 0.0

    def set_state(self, state: str) -> None:
        if state not in frames():
            raise ValueError(f'Unknown mascot state: {state}')
        changed = state != self.state
        self.state = state
        descriptions = {'ready': 'готов', 'listening': 'слушает', 'thinking': 'думает', 'error': 'ошибка'}
        self.setAccessibleName(f'Маскот Eidos: {descriptions[state]}')
        self.update()
        if changed and self.animations_enabled and self.isVisible():
            self.animation.stop()
            self.animation.start()

    def hideEvent(self, event) -> None:
        self.animation.stop()
        self._offset = 0
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        size = min(self.width(), self.height())
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2 + self._offset, size, size)
        frame = frames()[self.state]
        painter.drawPixmap(rect, frame, QRectF(frame.rect()))
