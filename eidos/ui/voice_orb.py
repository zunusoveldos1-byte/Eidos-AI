"""Accessible microphone button with quiet idle and real audio driven waves."""
import math
from PyQt6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation
from PyQt6.QtGui import QColor, QPainter, QPen
from eidos.ui.localized import QPushButton
from .icons import icon

TITLES = {'ready': 'Готов', 'listening': 'Слушаю', 'thinking': 'Обрабатываю',
          'acting': 'Обрабатываю', 'speaking': 'Говорю', 'paused': 'На паузе', 'error': 'Ошибка'}
ACTIONS = {'ready': 'Начать голосовой ввод', 'listening': 'Закончить запись и обработать',
           'speaking': 'Приостановить озвучку', 'paused': 'Продолжить озвучку',
           'thinking': 'Обрабатываю · для отмены нажмите «Остановить»',
           'acting': 'Обрабатываю · для отмены нажмите «Остановить»', 'error': 'Повторить голосовой ввод'}

MIC_TITLES = {'inactive': 'Микрофон не записывает', 'enabled': 'Прослушивание включено',
              'waiting': 'Жду: „Эйдос“', 'recording': 'Слушаю вас',
              'off': 'Микрофон выключен', 'error': 'Ошибка микрофона'}
MIC_COLORS = {'inactive': '#355C4A', 'enabled': '#18513A', 'waiting': '#18432F',
              'recording': '#18513A', 'off': '#39423E', 'error': '#554321'}


class VoiceOrb(QPushButton):
    def __init__(self, size=230, parent=None):
        super().__init__(parent)
        self.state = 'ready'
        self.microphone_state = 'inactive'
        self.microphone_error = ''
        self.level = self._display_level = self.speech_level = self._speech_level = 0.
        self.animations_enabled = True
        self.phase = 0.
        self._color = QColor(MIC_COLORS['inactive'])
        self._ring_scale = .94
        self.transition = QVariantAnimation(self)
        self.transition.setDuration(200)
        self.transition.setStartValue(0.)
        self.transition.setEndValue(1.)
        self.transition.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.transition.valueChanged.connect(self._blend)
        self.pulse = QVariantAnimation(self)
        self.pulse.setStartValue(0.)
        self.pulse.setEndValue(math.tau)
        self.pulse.setLoopCount(-1)
        self.pulse.valueChanged.connect(self._pulse)
        self.setFixedSize(size, size)
        self.setStyleSheet(f'QPushButton {{ background: transparent; border: none; padding: 0px; '
                           f'min-width: {size}px; max-width: {size}px; min-height: {size}px; max-height: {size}px; }}')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.visual_timer = QTimer(self)
        self.visual_timer.setInterval(33)
        self.visual_timer.timeout.connect(self._animate)
        self.set_state('ready')

    def set_microphone(self, state, error=''):
        state = state if state in MIC_TITLES else 'inactive'
        changed = state != self.microphone_state
        self.microphone_state, self.microphone_error = state, error
        if changed:
            self.level = self._display_level = 0.
            self.transition.stop()
            self._from_color = QColor(self._color)
            self._to_color = QColor(MIC_COLORS[state])
            self._from_ring = self._ring_scale
            self._to_ring = 1. if state in ('enabled', 'waiting', 'recording') else .94
            if self.animations_enabled and self.isVisible() and state != 'error':
                self.transition.start()
            else:
                self._blend(1.)
        self._accessibility()
        self._sync_timer()
        self.update()

    def _blend(self, value):
        if not hasattr(self, '_from_color'):
            return
        start, end = self._from_color, self._to_color
        self._color = QColor(*(round(a + (b - a) * value) for a, b in
                               zip(start.getRgb(), end.getRgb())))
        self._ring_scale = self._from_ring + (self._to_ring - self._from_ring) * value
        self.update()

    def _pulse(self, value):
        self.phase = value
        self.update()

    def _accessibility(self):
        self.setText('Выключить голосовой режим' if self.microphone_state != 'off' else 'Включить голосовой режим')
        self.setAccessibleName(ACTIONS[self.state])
        status = MIC_TITLES[self.microphone_state]
        self.setAccessibleDescription(status + (' · ' + self.microphone_error if self.microphone_error else ''))
        self.setToolTip(ACTIONS[self.state] + '\n' + status +
                       ('\n' + self.microphone_error if self.microphone_error else '') + '\nПробел / Enter при фокусе')

    def set_state(self, state):
        if state not in TITLES:
            state = 'thinking'
        if state != self.state:
            self.level = self._display_level = 0.
        self.state = state
        self._accessibility()
        self._sync_timer()
        self.update()

    def set_level(self, level):
        self.level = max(0., min(1., float(level))) if math.isfinite(level) else 0.
        self.update()

    def set_speech_level(self, level):
        self.speech_level = max(0., min(1., float(level))) if math.isfinite(level) else 0.
        self.update()

    def set_animations(self, enabled):
        self.animations_enabled = bool(enabled)
        if not self.animations_enabled:
            self.transition.stop()
            self._blend(1.)
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        visible = self.isVisible() and self.animations_enabled
        mic_motion = self.microphone_state in ('enabled', 'waiting', 'recording')
        speech_motion = self.state == 'speaking'
        if visible and (mic_motion or speech_motion):
            duration = 4200 if self.microphone_state == 'waiting' else 2800
            if self.pulse.duration() != duration:
                self.pulse.stop()
                self.pulse.setDuration(duration)
            if self.pulse.state() != QVariantAnimation.State.Running:
                self.pulse.start()
            if self.microphone_state == 'recording' or speech_motion:
                self.visual_timer.start()
            else:
                self.visual_timer.stop()
        else:
            self.pulse.stop()
            self.visual_timer.stop()

    def _animate(self):
        self._display_level += (self.level - self._display_level) * .28
        self._speech_level += (self.speech_level - self._speech_level) * .28
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        self.visual_timer.stop()
        self.pulse.stop()
        self.transition.stop()
        self._blend(1.)
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.isAutoRepeat():
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        base = self.width() * .235
        phase = self.phase if self.animations_enabled else 0.
        mic = self.microphone_state
        audio = min(1., self._display_level * 9.) if mic == 'recording' and self.animations_enabled else 0.
        calm = 1.8 if mic in ('enabled', 'waiting') and self.animations_enabled else 0.
        ring_color = '#E3B65A' if mic == 'error' else '#74877C' if mic in ('off', 'inactive') else '#2FE09B'
        for i in range(4):
            radius = (base + 12 + i * 10) * self._ring_scale + audio * (6 + i * 3) + calm * math.sin(phase - i * .5)
            radius = min(self.width() / 2 - 3, radius)
            color = QColor(ring_color)
            color.setAlpha(max(18, (88 if mic in ('enabled', 'waiting', 'recording') else 65) - i * 17))
            painter.setPen(QPen(color, 1.3 + audio))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(c, radius, radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(c, base, base)
        if self.hasFocus():
            painter.setPen(QPen(QColor('#F2F6F3'), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(c, base + 5, base + 5)
        glyph = '#E3B65A' if mic == 'error' else '#B1BDB6' if mic in ('off', 'inactive') else '#41E4A0'
        icon('mic', glyph).paint(painter, int(c.x() - min(20, base*.5)), int(c.y() - min(24, base*.6)), int(min(40, base)), int(min(40, base)))
        if mic == 'off':
            painter.setPen(QPen(QColor(glyph), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(c.x() - 20, c.y() - 23), QPointF(c.x() + 20, c.y() + 14))
        if self.state in ('speaking', 'paused'):
            # Separate response sound bars; these never claim microphone capture.
            painter.setPen(QPen(QColor('#7FE0B0'), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(5):
                height = 3.
                if self.state == 'speaking' and self.animations_enabled:
                    height += 8 * min(1., self._speech_level * 10) + 2 * (1 + math.sin(phase * 2 + i))
                x, y = c.x() + (i - 2) * 7, c.y() + 30
                painter.drawLine(QPointF(x, y - height / 2), QPointF(x, y + height / 2))
