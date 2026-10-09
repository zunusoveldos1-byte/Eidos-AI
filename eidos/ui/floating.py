"""Optional floating voice controls; application owns visibility and persistence."""
from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QCheckBox, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .mascot import Mascot, STATE_DESCRIPTIONS


def clamp_position(position: QPoint, size: QSize, available: list[QRect]) -> QPoint:
    """Keep the widget on the nearest available screen, in logical coordinates."""
    if not available:
        return QPoint(position)
    candidates = []
    for rect in available:
        x = max(rect.left(), min(position.x(), rect.left() + max(0, rect.width() - size.width())))
        y = max(rect.top(), min(position.y(), rect.top() + max(0, rect.height() - size.height())))
        candidates.append(QPoint(x, y))
    return min(candidates, key=lambda p: (p.x() - position.x()) ** 2 + (p.y() - position.y()) ** 2)


class FloatingMascot(QWidget):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    open_requested = pyqtSignal()
    position_changed = pyqtSignal(int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('Eidos — голосовой помощник')
        self.setAccessibleName('Плавающий голосовой виджет Eidos')
        self.setObjectName('floatingMascot')
        self.setStyleSheet('''
            QWidget#floatingMascot { background: #151B18; border: 1px solid #35453C; border-radius: 14px; }
            QLabel, QCheckBox { color: #F2F6F3; background: transparent; }
            QPushButton { color: #F2F6F3; background: #202925; border: 1px solid #35453C;
                border-radius: 7px; padding: 7px; }
            QPushButton:hover { background: #2B3932; }
            QPushButton:focus { border: 2px solid #2FE09B; }
        ''')
        self._drag_offset = None
        self._drag_moved = False
        self.mascot = Mascot(140)
        self.mascot.setParent(self)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(38)
        self.status_label.setMaximumHeight(80)
        self.start_button = QPushButton('Начать запись')
        self.stop_button = QPushButton('Стоп / остановить речь')
        self.pause_button = QPushButton('Пауза микрофона')
        self.open_button = QPushButton('Открыть Eidos')
        self.pin_checkbox = QCheckBox('Поверх окон')
        controls = QGridLayout()
        for index, name in enumerate(('start', 'stop', 'pause', 'open')):
            button = getattr(self, name + '_button')
            button.setAccessibleName(button.text())
            button.clicked.connect(getattr(self, name + '_requested').emit)
            controls.addWidget(button, index // 2, index % 2)
        self.pin_checkbox.toggled.connect(self.set_pinned)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.addWidget(self.mascot, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.status_label)
        layout.addLayout(controls)
        layout.addWidget(self.pin_checkbox)
        self.setFixedWidth(320)
        self.adjustSize()
        self.mascot.installEventFilter(self)
        self.status_label.installEventFilter(self)
        self.set_status('ready', '')

    def set_status(self, state: str, message: str = '') -> None:
        self.mascot.set_state(state)
        status = STATE_DESCRIPTIONS[state].capitalize()
        self.status_label.setText(status + ('\n' + message if message else ''))
        self.status_label.setToolTip(message)
        self.status_label.setAccessibleName(self.status_label.text())
        self.setAccessibleDescription(self.status_label.text())
        self.pause_button.setText('Возобновить микрофон' if state == 'paused' else 'Пауза микрофона')
        self.pause_button.setAccessibleName(self.pause_button.text())

    def set_level(self, value: float) -> None:
        self.mascot.set_level(value)

    def restore_position(self, x: int, y: int) -> None:
        screens = [screen.availableGeometry() for screen in QApplication.screens()]
        self.move(clamp_position(QPoint(x, y), self.size(), screens))

    def set_pinned(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.pin_checkbox.blockSignals(True)
        self.pin_checkbox.setChecked(enabled)
        self.pin_checkbox.blockSignals(False)
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) == enabled:
            return
        visible = self.isVisible()
        position = self.pos()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.move(position)
        if visible:
            self.show()

    def _drag_event(self, event) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.pos()
            self._drag_moved = False
            return True
        if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
            target = event.globalPosition().toPoint() - self._drag_offset
            self._drag_moved = self._drag_moved or target != self.pos()
            self.move(target)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            target = event.globalPosition().toPoint() - self._drag_offset
            moved = self._drag_moved or target != self.pos()
            self.move(target)
            self._drag_offset = None
            if moved:
                self.restore_position(self.x(), self.y())
                self.position_changed.emit(self.x(), self.y())
            return True
        return False

    def eventFilter(self, watched, event) -> bool:
        if watched in (self.mascot, self.status_label) and self._drag_event(event):
            return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:
        if not self._drag_event(event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if not self._drag_event(event):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if not self._drag_event(event):
            super().mouseReleaseEvent(event)
