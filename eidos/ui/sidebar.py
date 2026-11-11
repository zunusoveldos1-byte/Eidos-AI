"""Eight destinations; stable IDs for existing voice commands."""
from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, pyqtSignal, pyqtProperty
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QButtonGroup, QScrollArea, QVBoxLayout
from eidos.ui.localized import QPushButton, QWidget
from .components import label
from .icons import icon
from .theme import ACCENT, SECONDARY, TEXT

NAMES = ('Главная', 'Экран и перевод', 'Камера и жесты', 'Инструменты', 'Настройки')
ICONS = ('home', 'languages', 'camera', 'list', 'settings')
PAGE_IDS = (0, 3, 2, 6, 4)


class NavigationButton(QPushButton):
    """Paint navigation states explicitly, independent of native hover fills."""
    def __init__(self, title, symbol):
        super().__init__('  ' + title)
        self._symbol = symbol
        self.setIcon(icon(symbol, SECONDARY))
        self._normal_icon = icon(symbol, SECONDARY).pixmap(20, 20)
        self._accent_icon = icon(symbol, ACCENT).pixmap(20, 20)
        self._hover = 0.
        self.motion_enabled = True
        self._text_color = QColor(TEXT)
        self._normal = QColor(TEXT)
        self._accent = QColor(ACCENT)
        self._border = QPen(self._accent, 1)
        self._focus_pen = QPen(QColor('#63F3CB'), 1.5, Qt.PenStyle.DashLine)
        self._selected_fill = QColor('#0D3B2C')
        self._rect = QRectF()
        self._focus_rect = QRectF()
        self._text_rect = QRectF()
        self._font = QFont('Inter')
        self._font.setPixelSize(13)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.animation = QPropertyAnimation(self, b'hover', self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def apply_theme(self, theme, accent):
        light = theme == 'light'
        self._normal = QColor('#15291F' if light else TEXT)
        self._accent = QColor(accent).darker(150) if light else QColor(accent)
        self._border = QPen(self._accent, 1)
        self._focus_pen = QPen(self._accent, 1.5, Qt.PenStyle.DashLine)
        self._selected_fill = QColor('#DDECE4' if light else '#0D3B2C')
        self._normal_icon = icon(self._symbol, '#486456' if light else SECONDARY).pixmap(20, 20)
        self._accent_icon = icon(self._symbol, self._accent.name()).pixmap(20, 20)
        self.update()

    @pyqtProperty(float)
    def hover(self):
        return self._hover

    @hover.setter
    def hover(self, value):
        self._hover = value
        self.update()

    def set_animations(self, enabled):
        self.motion_enabled = bool(enabled)
        if not enabled:
            self.animation.stop()
            self.hover = 1. if self.underMouse() else 0.

    def _target(self, value):
        self.animation.stop()
        if self.motion_enabled:
            self.animation.setStartValue(self.hover)
            self.animation.setEndValue(value)
            self.animation.start()
        else:
            self.hover = value

    def enterEvent(self, event):
        self._target(1.)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._target(0.)
        super().leaveEvent(event)

    def hideEvent(self, event):
        self.animation.stop()
        self.hover = 0.
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._rect.setRect(.5, .5, self.width() - 1, self.height() - 1)
        if self.isChecked():
            painter.setBrush(self._selected_fill)
            painter.setPen(self._border)
            painter.drawRoundedRect(self._rect, 13, 13)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self._focus_pen)
            self._focus_rect.setRect(3, 3, self.width() - 6, self.height() - 6)
            painter.drawRoundedRect(self._focus_rect, 10, 10)
        fraction = 1. if self.isChecked() else self.hover
        painter.setOpacity(1 - fraction)
        painter.drawPixmap(10, (self.height() - 20) // 2, self._normal_icon)
        painter.setOpacity(fraction)
        painter.drawPixmap(10, (self.height() - 20) // 2, self._accent_icon)
        painter.setOpacity(1.)
        for channel in ('Red', 'Green', 'Blue'):
            source = getattr(self._normal, channel.lower())()
            target = getattr(self._accent, channel.lower())()
            getattr(self._text_color, 'set' + channel)(round(source + (target - source) * fraction))
        painter.setPen(self._text_color)
        self._font.setWeight(QFont.Weight.DemiBold if self.isChecked() else QFont.Weight.Normal)
        painter.setFont(self._font)
        self._text_rect.setRect(40, 0, self.width() - 48, self.height())
        painter.drawText(self._text_rect, Qt.AlignmentFlag.AlignVCenter, self.text().strip())


class Sidebar(QWidget):
    selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName('sidebar')
        self.setFixedWidth(240)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName('sidebarScroll')
        scroll.viewport().setObjectName('sidebarViewport')
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        panel = QWidget()
        panel.setObjectName('sidebarContent')
        scroll.setWidget(panel)
        outer.addWidget(scroll)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 24, 14, 20)
        layout.setSpacing(6)
        layout.addWidget(label('Eidos', 'brand'))
        layout.addWidget(label('Ваш рабочий помощник', 'muted'))
        layout.addSpacing(20)
        self.page_ids = PAGE_IDS
        self.group = QButtonGroup(self)
        self.buttons = []
        for name, image, page_id in zip(NAMES, ICONS, PAGE_IDS):
            control = NavigationButton(name, image)
            control.setObjectName('nav')
            control.setStyleSheet('font-size: 13px; padding: 13px 8px;')
            control.setCheckable(True)
            control.setIconSize(QSize(20, 20))
            control.setAccessibleName(name)
            control.setToolTip('' if page_id == 5 else name)
            self.group.addButton(control, page_id)
            self.buttons.append(control)
            layout.addWidget(control)
        layout.addStretch()
        self.group.idClicked.connect(self.selected)
        self.activate(0)

    def activate(self, index):
        for image, page_id, control in zip(ICONS, PAGE_IDS, self.buttons):
            control.setChecked(page_id == index)
            control.setIcon(icon(image, ACCENT if page_id == index else SECONDARY))

    def set_animations(self, enabled):
        for control in self.buttons:
            control.set_animations(enabled)


class SidebarHost(QWidget):
    """Clip a stable-width menu while letting the main layout reclaim its space."""
    def __init__(self, sidebar):
        super().__init__()
        self.sidebar = sidebar
        sidebar.setParent(self)
        self.panelWidth = 240

    @pyqtProperty(int)
    def panelWidth(self):
        return self.width()

    @panelWidth.setter
    def panelWidth(self, value):
        self.setFixedWidth(value)
        self.sidebar.move(value - 240, 0)

    def resizeEvent(self, event):
        self.sidebar.resize(240, self.height())
        super().resizeEvent(event)
