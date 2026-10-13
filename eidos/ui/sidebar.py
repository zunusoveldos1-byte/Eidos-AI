"""Eight destinations; stable IDs for existing voice commands."""
from PyQt6.QtCore import QSize, pyqtSignal, pyqtProperty
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QButtonGroup, QScrollArea, QVBoxLayout, QWidget
from .components import button, label
from .icons import icon
from .theme import ACCENT, SECONDARY

NAMES = ('Главная', 'Диалог', 'Голос', 'Экран и перевод', 'Камера и жесты', 'Инструменты', 'Память', 'Настройки')
ICONS = ('home', 'message', 'mic', 'languages', 'camera', 'list', 'user', 'settings')
PAGE_IDS = (0, 5, 1, 3, 2, 6, 7, 4)


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
            control = button('  ' + name, image)
            control.setObjectName('nav')
            control.setStyleSheet('font-size: 13px; padding: 13px 8px;')
            control.setCheckable(True)
            control.setIconSize(QSize(20, 20))
            control.setAccessibleName(name)
            control.setToolTip(name)
            self.group.addButton(control, page_id)
            self.buttons.append(control)
            layout.addWidget(control)
        self.assistant_button = self.group.button(5)
        layout.addStretch()
        self.group.idClicked.connect(self.selected)
        self.activate(0)

    def activate(self, index):
        for image, page_id, control in zip(ICONS, PAGE_IDS, self.buttons):
            control.setChecked(page_id == index)
            control.setIcon(icon(image, ACCENT if page_id == index else SECONDARY))


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
