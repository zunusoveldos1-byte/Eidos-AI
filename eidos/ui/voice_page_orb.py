"""Main voice visualization driven exclusively by the existing capture VAD."""
import math
import time
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from .icons import icon
from .voice_orb import VoiceOrb


def error_copy(message):
    text = message.lower()
    if any(word in text for word in ('permission', 'denied', 'нет доступа', 'отказ', 'запрещ')):
        return 'Нет доступа к микрофону', 'Разрешите доступ в настройках Windows'
    if any(word in text for word in ('not found', 'no device', 'removed', 'не найден', 'отключён', 'подключите')) or ('устройств' in text and 'подключ' in text):
        return 'Микрофон не найден', 'Подключите микрофон и проверьте устройство в настройках'
    if any(word in text for word in ('connection', 'connect', 'network', 'подключени', 'интернет')):
        return 'Нет подключения', 'Проверьте подключение к выбранному сервису'
    return 'Сервис недоступен', 'Проверьте параметры голоса в настройках'


class VoicePageOrb(VoiceOrb):
    presentation_changed = pyqtSignal()

    def __init__(self, size=250):
        self.ui_state = 'off'
        self.sleeping = self.wake_ready = False
        self.message = ''
        self._last_audio = self._last_frame = time.monotonic()
        self._voice_target = 0.
        super().__init__(size)
        self._color = QColor('#39423E')
        self._paths = [QPainterPath() for _ in range(4)]
        self._pens = [QPen(QColor('#74877C'), 1.2) for _ in range(4)]
        self._ring_color = QColor('#74877C')
        self._center = QPointF(size / 2, size / 2)
        self._glyphs = {s: icon('mic', '#2FE09B' if s == 'active' else '#E3B65A' if s == 'error' else '#A9B5AE').pixmap(42, 42)
                        for s in ('active', 'sleep', 'error', 'off')}
        self._moon = icon('moon', '#A9B5AE').pixmap(18, 18)
        self._warning = icon('warning', '#E3B65A').pixmap(18, 18)
        self.pulse.stop()

    def set_context(self, sleeping=False, wake_ready=False):
        self.sleeping, self.wake_ready = sleeping, wake_ready
        self._presentation()

    def copy(self):
        if self.ui_state == 'active':
            return 'Слушаю вас', ''
        if self.ui_state == 'sleep':
            return 'Спит', 'Разбудите голосом' if self.wake_ready else 'Нажмите, чтобы разбудить'
        if self.ui_state == 'error':
            return error_copy(self.microphone_error or self.message)
        return 'Микрофон выключен', 'Нажмите, чтобы включить'

    def _presentation(self):
        state = ('error' if self.microphone_state == 'error' else
                 'sleep' if self.sleeping or self.microphone_state == 'waiting' else
                 'active' if self.microphone_state in ('enabled', 'recording') else
                 'error' if self.state == 'error' and self.message else 'off')
        changed = state != self.ui_state
        self.ui_state = state
        if changed:
            self.transition.stop()
            self._from_color = QColor(self._color)
            self._to_color = QColor({'active': '#102B20', 'sleep': '#29352F', 'off': '#39423E', 'error': '#453A28'}[state])
            self._from_ring = self._to_ring = 1.
            if self.animations_enabled and self.isVisible():
                self.transition.start()
            else:
                self._blend(1.)
        self._accessibility()
        self._sync_timer()
        self.presentation_changed.emit()
        self.update()

    def _accessibility(self):
        title, hint = self.copy()
        action = 'Выключить голосовой режим' if self.ui_state == 'active' else 'Разбудить голосовой режим' if self.ui_state == 'sleep' else 'Включить голосовой режим'
        self.setText(action)
        self.setAccessibleName(action)
        self.setAccessibleDescription(title + (' · ' + hint if hint else ''))
        self.setToolTip(self.microphone_error or action)

    def set_microphone(self, state, error=''):
        if state != self.microphone_state:
            self.level = self._voice_target = self._display_level = 0.
        self.microphone_state, self.microphone_error = state, error
        if state in ('enabled', 'recording'):
            self.message = ''
        self._presentation()

    def set_state(self, state):
        super().set_state(state)
        self._presentation()

    def set_message(self, message):
        self.message = message
        self._presentation()

    def set_level(self, value):
        # RMS alone never starts motion. Capture VAD supplies the paired signal.
        self.level = float(value) if math.isfinite(value) else 0.

    def set_voice_activity(self, rms, speaking):
        rms = float(rms)
        self._last_audio = time.monotonic()
        allowed = self.ui_state == 'active' and self.state != 'speaking'
        self._voice_target = min(1., max(0., rms * 12)) if speaking and allowed and math.isfinite(rms) else 0.
        self._sync_timer()

    def set_speech_level(self, value):
        self.speech_level = value  # Reply audio cannot animate user voice waves.

    def _sync_timer(self):
        self.pulse.stop()
        allowed = self.isVisible() and not self.window().isMinimized() and self.animations_enabled and self.ui_state == 'active' and self.state != 'speaking'
        if allowed and (self._voice_target > 0 or self._display_level > .02):
            if not self.visual_timer.isActive():
                self._last_frame = time.monotonic()
                self.visual_timer.start()
        else:
            self.visual_timer.stop()
            if not allowed:
                self._voice_target = self._display_level = 0.

    def _animate(self):
        now = time.monotonic()
        delta = min(.1, now - self._last_frame)
        self._last_frame = now
        if now - self._last_audio > .24:
            self._voice_target = 0.
        tau = .045 if self._voice_target > self._display_level else .09
        self._display_level += (self._voice_target - self._display_level) * (1 - math.exp(-delta / tau))
        if self._voice_target == 0 and self._display_level < .02:
            self._display_level = 0.
            self.visual_timer.stop()
        else:
            self.phase += delta * (1.2 + self._display_level)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self._center
        base = self.width() * .235
        amplitude = self._display_level if self.animations_enabled else 0.
        color = '#2FE09B' if self.ui_state == 'active' else '#E3B65A' if self.ui_state == 'error' else '#74877C'
        self._ring_color.setNamedColor(color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, path in enumerate(self._paths):
            radius = base + 14 + index * 10
            path.clear()
            for point in range(65):
                theta = point * math.tau / 64
                distortion = amplitude * (3 + index * 1.6) * (math.sin(theta * 3 + self.phase + index * .7) + .45 * math.cos(theta * 5 - self.phase * .6))
                r = radius + distortion
                x, y = center.x() + r * math.cos(theta), center.y() + r * math.sin(theta)
                if point == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.closeSubpath()
            self._ring_color.setAlpha((78 if self.ui_state == 'active' else 40) - index * 8)
            self._pens[index].setColor(self._ring_color)
            self._pens[index].setWidthF(1.2)
            painter.setPen(self._pens[index])
            painter.drawPath(path)
            if self.ui_state == 'active':
                self._ring_color.setAlpha(round(5 + amplitude * 7))
                self._pens[index].setColor(self._ring_color)
                self._pens[index].setWidthF(7.)
                painter.setPen(self._pens[index])
                painter.drawPath(path)
        painter.setBrush(self._color)
        self._ring_color.setAlpha(130 if self.ui_state in ('active', 'error') else 30)
        self._pens[0].setColor(self._ring_color)
        self._pens[0].setWidthF(1.2)
        painter.setPen(self._pens[0])
        painter.drawEllipse(center, base, base)
        painter.drawPixmap(int(center.x() - 21), int(center.y() - 21), self._glyphs[self.ui_state])
        if self.ui_state == 'off':
            self._ring_color.setNamedColor('#A9B5AE')
            self._pens[0].setColor(self._ring_color)
            self._pens[0].setWidthF(2.5)
            painter.setPen(self._pens[0])
            painter.drawLine(int(center.x() - 24), int(center.y() - 24), int(center.x() + 24), int(center.y() + 24))
        if self.ui_state in ('sleep', 'error'):
            painter.drawPixmap(int(center.x() + base - 6), int(center.y() - base + 2), self._moon if self.ui_state == 'sleep' else self._warning)
        if self.hasFocus():
            self._ring_color.setNamedColor('#F2F6F3')
            self._pens[0].setColor(self._ring_color)
            self._pens[0].setWidthF(1.5)
            painter.setPen(self._pens[0])
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, base + 5, base + 5)
