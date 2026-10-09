from PyQt6.QtCore import QSize, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget
from .components import button, label
from .icons import icon
from .mascot import Mascot
from .theme import ACCENT, SECONDARY

NAMES = ('Главная', 'Голос', 'Жесты', 'Перевод', 'Настройки')
ICONS = ('home', 'mic', 'hand', 'languages', 'settings')


class Sidebar(QWidget):
    selected = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('sidebar')
        self.setFixedWidth(218)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 24, 14, 24)
        layout.setSpacing(8)
        brand = QHBoxLayout()
        self.logo = Mascot(48)
        self.logo.setFixedWidth(48)
        brand.addWidget(self.logo)
        brand.addWidget(label('Eidos', 'brand'), 1)
        layout.addLayout(brand)
        layout.addSpacing(26)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = []
        for index, name in enumerate(NAMES):
            if index == 1:
                layout.addSpacing(16)
                layout.addWidget(label('  Разделы', 'muted'))
            if index == 4:
                layout.addStretch()
                self.mascot = Mascot(130)
                layout.addWidget(self.mascot)
                layout.addSpacing(10)
            widget = button('  ' + name, ICONS[index])
            widget.setObjectName('nav')
            widget.setCheckable(True)
            widget.setIconSize(QSize(23, 23))
            widget.setAccessibleName(name)
            widget.setToolTip(f'Открыть раздел «{name}»')
            self.group.addButton(widget, index)
            self.buttons.append(widget)
            layout.addWidget(widget)
        self.group.idClicked.connect(self.selected)
        self.activate(0)

    def activate(self, index: int) -> None:
        self.buttons[index].setChecked(True)
        for item, widget in enumerate(self.buttons):
            widget.setIcon(icon(ICONS[item], ACCENT if item == index else SECONDARY))
