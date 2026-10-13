"""Emerald home; one clock for the purely decorative scene."""
import math
import time

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, QRectF, QSize, Qt, QTimer, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget
from ..components import ResponsiveRow, button, label
from ..icons import icon
from ..theme import ASSETS


class RevealEffect(QGraphicsOpacityEffect):
    def __init__(self, parent):
        super().__init__(parent)
        self._shift = 0.

    @pyqtProperty(float)
    def shift(self):
        return self._shift

    @shift.setter
    def shift(self, value):
        self._shift = value
        self.update()

    def draw(self, painter):
        painter.save()
        painter.translate(0, self._shift)
        super().draw(painter)
        painter.restore()


class ActionCard(QPushButton):
    """Paint transforms inside safe margins, keeping hit targets stable."""
    def __init__(self, title, symbol, hint, tint='#25E6A1'):
        super().__init__(title)
        self.symbol, self.tint = symbol, tint
        self._hover = 0.
        self.motion_enabled = True
        self.setObjectName('homeAction')
        self.setMinimumHeight(106)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(hint)
        self.setAccessibleName(title)
        self.animation = QPropertyAnimation(self, b'hover', self)
        self.animation.setDuration(170)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, value):
        self._hover = value
        self.update()

    def set_motion(self, enabled):
        self.motion_enabled = enabled
        if not enabled:
            self.animation.stop()
            self.hover = 0.

    def _animate_hover(self, value):
        self.animation.stop()
        if self.motion_enabled:
            self.animation.setStartValue(self.hover)
            self.animation.setEndValue(value)
            self.animation.start()
        else:
            self.hover = value

    def enterEvent(self, event):
        self._animate_hover(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.)
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(0, -3 * self.hover + (2 if self.isDown() else 0))
        rect = QRectF(1, 6, self.width() - 2, self.height() - 12)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor('#0D3025'))
        gradient.setColorAt(1, QColor('#0B2620'))
        painter.setBrush(gradient)
        stroke = QColor(self.tint)
        stroke.setAlphaF(.3 + .35 * self.hover if not self.hasFocus() else .9)
        painter.setPen(QPen(stroke, 1.2))
        painter.drawRoundedRect(rect, 18, 18)
        tile = QRectF(18, 27, 52, 52)
        color = QColor(self.tint)
        color.setAlpha(20 + int(16 * self.hover))
        painter.setBrush(color)
        painter.setPen(QPen(stroke, 1))
        painter.drawRoundedRect(tile, 15, 15)
        painter.drawPixmap(30, 39, icon(self.symbol, self.tint, 28).pixmap(28, 28))
        painter.setPen(QColor('#F2FAF6'))
        font = QFont('Inter')
        font.setPixelSize(15 if self.width() < 300 else 17)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(QRectF(86, 18, max(0, self.width() - 106), 70), Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, self.text())


class HeroMascot(QWidget):
    def __init__(self):
        super().__init__()
        self.pixmap = QPixmap(str(ASSETS / 'eidos-home.png'))
        self.phase = 0.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setFixedHeight(330)
        self.setAccessibleName('Эйдос — белый робот с зелёным листом')

    def sizeHint(self):
        return QSize(320, 330)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(self.width() / 2, self.height() * .66, min(self.width(), self.height()) * .58)
        glow.setColorAt(0, QColor(37, 230, 161, 35))
        glow.setColorAt(1, QColor(37, 230, 161, 0))
        painter.fillRect(self.rect(), glow)
        size = self.pixmap.size().scaled(max(1, self.width() - 24), self.height() - 32, Qt.AspectRatioMode.KeepAspectRatio)
        offset = -2 * (1 - math.cos(self.phase * 2 * math.pi / 5))
        target = QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2 - 6 + offset, size.width(), size.height())
        painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        painter.setPen(QPen(QColor(37, 230, 161, 50), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(self.width() * .21, self.height() - 23, self.width() * .58, 15))


class HomeCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.phase = 0.
        self.setObjectName('homeCanvas')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#081D18'))
        glow = QRadialGradient(self.width() * .78, self.height() * .48, self.width() * .7)
        glow.setColorAt(0, QColor(13, 59, 44, 125))
        glow.setColorAt(1, QColor(8, 29, 24, 0))
        painter.fillRect(self.rect(), glow)
        for layer in range(3):
            path = QPainterPath()
            for i in range(81):
                x = self.width() * i / 80
                angle = i / 80 * 2 * math.pi + self.phase * 2 * math.pi / 16 + layer * .7
                y = self.height() - 80 - layer * 17 + math.sin(angle) * (23 + layer * 10 + 3 * math.sin(self.phase * 4 * math.pi / 16))
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            painter.setPen(QPen(QColor(37, 230, 161, 40 - layer * 10), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            path.lineTo(self.width(), self.height())
            path.lineTo(0, self.height())
            path.closeSubpath()
            fill = QLinearGradient(0, self.height() - 170, 0, self.height())
            fill.setColorAt(0, QColor(37, 230, 161, 12))
            fill.setColorAt(1, QColor(37, 230, 161, 0))
            painter.fillPath(path, fill)
        for index in range(7):
            progress = (self.phase / (11 + index) + index / 7) % 1
            alpha = int(45 * math.sin(progress * math.pi) ** 2)
            x = self.width() * (.12 + index * .127)
            y = self.height() * (1 - progress)
            painter.setPen(QPen(QColor(37, 230, 161, alpha), 1))
            if index % 3 == 0:
                painter.drawLine(int(x), int(y), int(x), int(y + 22))
            else:
                painter.setBrush(QColor(37, 230, 161, alpha))
                painter.drawEllipse(QRectF(x, y, 2, 2))


class HomePage(QWidget):
    navigate_requested = pyqtSignal(int)
    compact_requested = pyqtSignal()
    conversation_requested = pyqtSignal()
    capture_requested = pyqtSignal()
    task_requested = pyqtSignal(str)
    app_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName('homePage')
        self.animations_enabled = True
        self._elapsed = 0.
        self._last_tick = time.monotonic()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setObjectName('homeViewport')
        self.scroll.viewport().setStyleSheet('QWidget#homeViewport { background: #081D18; }')
        self.content = HomeCanvas()
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(38, 24, 38, 32)
        self.body.setSpacing(24)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)
        camera_row = QHBoxLayout()
        camera_row.addStretch()
        self.camera_status = button('Камера: выкл.', 'camera')
        self.camera_status.setObjectName('cameraStatus')
        self.camera_status.setToolTip('Открыть камеру и жесты. Устройство включается в этом разделе.')
        self.camera_status.clicked.connect(lambda: self.navigate_requested.emit(2))
        camera_row.addWidget(self.camera_status)
        self.body.addLayout(camera_row)
        self.body.addStretch(2)
        left = QWidget()
        left.setMinimumWidth(0)
        text = QVBoxLayout(left)
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(22)
        text.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.title = label('Привет, я Eidos', 'homeTitle')
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.title.setText('Привет, я <span style="color:#25E6A1">Eidos</span>')
        self.title.setAccessibleName('Привет, я Eidos')
        text.addWidget(self.title)
        self.status = label('●  Готов помочь', 'homeStatus')
        self.status.setToolTip('Готов помочь')
        self.status.setMaximumWidth(210)
        self.status.setFixedHeight(38)
        text.addWidget(self.status)
        text.addSpacing(18)
        composer = QFrame()
        composer.setObjectName('homeComposer')
        composer.setMinimumHeight(90)
        row = QHBoxLayout(composer)
        row.setContentsMargins(12, 12, 12, 12)
        self.mic_button = button('', 'mic')
        self.mic_button.setObjectName('homeMic')
        self.mic_button.setFixedSize(52, 52)
        self.mic_button.setToolTip('Начать голосовой ввод')
        self.mic_button.setAccessibleName('Начать голосовой ввод')
        self.mic_button.clicked.connect(self.conversation_requested)
        row.addWidget(self.mic_button)
        self.input = QLineEdit()
        self.input.setObjectName('homeInput')
        self.input.setPlaceholderText('Что сделать?')
        self.input.setAccessibleName('Что сделать?')
        self.input.setMaxLength(12000)
        self.input.setMinimumWidth(0)
        row.addWidget(self.input, 1)
        self.send_button = button('', 'send', True)
        self.send_button.setFixedSize(52, 52)
        self.send_button.setToolTip('Отправить · Enter')
        self.send_button.setAccessibleName('Отправить')
        self.send_button.clicked.connect(self.submit)
        self.input.returnPressed.connect(self.submit)
        row.addWidget(self.send_button)
        text.addWidget(composer)
        self.hero_mascot = HeroMascot()
        self.hero = ResponsiveRow([left, self.hero_mascot], threshold=650, spacing=18)
        self.hero.row.setStretch(0, 7)
        self.hero.row.setStretch(1, 4)
        self.body.addWidget(self.hero)
        self.voice_button = ActionCard('Поговорить', 'message', 'Включить существующий голосовой режим и обсудить задачу.')
        self.translate_button = ActionCard('Перевести экран', 'scan', 'Выделить область экрана и получить перевод.', '#79C7D2')
        self.app_button = ActionCard('Открыть приложение', 'grid', 'Выбрать Блокнот или одно из разрешённых приложений.', '#B6A2EC')
        self.voice_button.clicked.connect(self.conversation_requested)
        self.translate_button.clicked.connect(self.capture_requested)
        self.app_button.clicked.connect(self.app_requested)
        self.actions = ResponsiveRow([self.voice_button, self.translate_button, self.app_button], threshold=650, spacing=14)
        self.body.addWidget(self.actions)
        self.body.addStretch(3)
        self.body.addSpacing(90)
        self.motion_timer = QTimer(self)
        self.motion_timer.setInterval(33)
        self.motion_timer.timeout.connect(self._tick)
        self.reveal_effect = RevealEffect(self.hero)
        self.hero.setGraphicsEffect(self.reveal_effect)
        self.reveal = QParallelAnimationGroup(self)
        for name, start, end in ((b'opacity', 0., 1.), (b'shift', 7., 0.)):
            animation = QPropertyAnimation(self.reveal_effect, name, self)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.setDuration(240)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.reveal.addAnimation(animation)

    def submit(self):
        text = self.input.text().strip()
        if text:
            self.task_requested.emit(text)

    def set_camera_status(self, text):
        lower = text.lower()
        if 'ошиб' in lower or 'недоступ' in lower or 'занят' in lower:
            state = 'ошибка'
        elif 'не удалось' in lower:
            state = 'ошибка'
        elif 'не найдена' in lower:
            state = 'не найдена'
        elif 'освобождаю' in lower:
            state = 'остановка…'
        elif 'выключена' in lower:
            state = 'выкл.'
        elif 'включена' in lower:
            state = 'вкл.'
        elif 'включаю' in lower or 'запуск' in lower:
            state = 'запуск…'
        else:
            state = 'проверка…'
        self.camera_status.setText('Камера: ' + state)
        self.camera_status.setToolTip(text + '\nОткрыть камеру и жесты')

    def set_animations(self, enabled):
        self.animations_enabled = bool(enabled)
        self.sync_motion()

    def sync_motion(self):
        enabled = self.animations_enabled and self.isVisible() and not self.window().isMinimized()
        for card in (self.voice_button, self.translate_button, self.app_button):
            card.set_motion(enabled)
        if enabled:
            self._last_tick = time.monotonic()
            self.motion_timer.start()
        else:
            self.motion_timer.stop()
            self.reveal.stop()
            self.reveal_effect.setOpacity(1.)
            self.reveal_effect.shift = 0.
            if not self.animations_enabled:
                self.content.phase = self.hero_mascot.phase = 0.
                self.content.update()
                self.hero_mascot.update()

    def _tick(self):
        now = time.monotonic()
        self._elapsed += min(.1, now - self._last_tick)
        self._last_tick = now
        self.content.phase = self.hero_mascot.phase = self._elapsed
        self.content.update()
        self.hero_mascot.update()

    def showEvent(self, event):
        super().showEvent(event)
        self.sync_motion()
        if self.motion_timer.isActive():
            self.reveal.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self.sync_motion()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        compact = self.width() < 700
        self.body.setContentsMargins(22 if compact else 38, 24, 22 if compact else 38, 32)
        self.hero_mascot.setFixedHeight(220 if compact else 330)
        self.title.setStyleSheet('font-family: "Comfortaa"; font-weight: 700; font-size: ' + ('32px;' if compact else '46px;'))
