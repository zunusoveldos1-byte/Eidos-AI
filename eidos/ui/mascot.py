"""Atlas mascot with optional low-rate animation and a real microphone meter.

The speaking overlay is a general activity indication, not lip synchronization.
"""
from functools import lru_cache
import math
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QPointF, QRectF, QSize, Qt, QTimer, pyqtProperty
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget
from .theme import ASSETS

STATE_DESCRIPTIONS = {
    'ready': 'готов', 'listening': 'слушает', 'thinking': 'думает',
    'acting': 'выполняет действие', 'speaking': 'говорит', 'error': 'ошибка',
    'paused': 'прослушивание отключено',
}


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
        self.level = 0.0
        self._tick = 0
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
        self.visual_timer = QTimer(self)
        self.visual_timer.setInterval(100)
        self.visual_timer.timeout.connect(self._animate)
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
        self.animations_enabled = bool(enabled)
        self._sync_animation()

    def _sync_animation(self) -> None:
        if self.animations_enabled and self.isVisible() and self.state not in ('error', 'paused'):
            self.visual_timer.start()
        else:
            self.visual_timer.stop()
            self.animation.stop()
            self.offset = 0.0
            self._tick = 0

    def _animate(self) -> None:
        self._tick = (self._tick + 1) % 600
        self.offset = -2.0 * (1 - math.cos(self._tick * math.pi / 20))

    def set_level(self, value: float) -> None:
        value = float(value)
        self.level = max(0.0, min(1.0, value)) if math.isfinite(value) else 0.0
        if self.state == 'listening':
            self.update()

    def set_state(self, state: str) -> None:
        if state not in STATE_DESCRIPTIONS:
            raise ValueError(f'Unknown mascot state: {state}')
        self.state = state
        self.setAccessibleName(f'Маскот Eidos: {STATE_DESCRIPTIONS[state]}')
        self.setAccessibleDescription('Общая анимация речи, без синхронизации губ' if state == 'speaking' else '')
        self.update()
        self._sync_animation()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_animation()

    def hideEvent(self, event) -> None:
        self.animation.stop()
        self.visual_timer.stop()
        self._offset = 0
        self._tick = 0
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height())
        rect = QRectF((self.width() - size) / 2, (self.height() - size) / 2 + self._offset, size, size)
        frame_state = {'acting': 'thinking', 'speaking': 'ready', 'paused': 'ready'}.get(self.state, self.state)
        frame = frames()[frame_state]
        painter.drawPixmap(rect, frame, QRectF(frame.rect()))
        # Brief deterministic eye closure; the atlas remains the only artwork.
        if self.animations_enabled and self.state == 'ready' and self._tick % 50 in (47, 48):
            for x in (0.475, 0.68):
                eye = QRectF(rect.x() + size * (x - .07), rect.y() + size * .515, size * .14, size * .095)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor('#104B3B'))
                painter.drawRoundedRect(eye, size * .03, size * .03)
                painter.setPen(QPen(QColor('#82FFC1'), max(2, size * .015)))
                painter.drawLine(eye.topLeft() + QPointF(0, eye.height()/2), eye.topRight() + QPointF(0, eye.height()/2))
        if self.state == 'acting':
            painter.setPen(QPen(QColor('#2FE09B'), 3))
            painter.drawArc(rect.adjusted(3, 3, -3, -3), (30 + self._tick * 12) * 16, 270 * 16)
        elif self.state == 'listening':
            meter = QRectF(rect.x() + size * .2, rect.bottom() - 8, size * .6, 5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#29362F'))
            painter.drawRoundedRect(meter, 2, 2)
            painter.setBrush(QColor('#2FE09B'))
            painter.drawRoundedRect(QRectF(meter.x(), meter.y(), meter.width() * self.level, meter.height()), 2, 2)
        elif self.state in ('thinking', 'speaking'):
            painter.setPen(Qt.PenStyle.NoPen)
            for index in range(3):
                active = self.animations_enabled and (self._tick // 3) % 3 == index
                painter.setBrush(QColor('#2FE09B' if active else '#A8B7AE'))
                radius = 3 + (1 if active and self.state == 'speaking' else 0)
                painter.drawEllipse(QRectF(rect.center().x() + (index - 1) * 12 - radius, rect.bottom() - 9 - radius, radius * 2, radius * 2))
        elif self.state == 'paused':
            icon = QRectF(rect.right() - 29, rect.bottom() - 34, 14, 22)
            painter.setPen(QPen(QColor('#A8B7AE'), 2))
            painter.setBrush(QColor('#151B18'))
            painter.drawRoundedRect(icon, 7, 7)
            painter.setPen(QPen(QColor('#E4BC76'), 3))
            painter.drawLine(icon.bottomLeft(), icon.topRight())
