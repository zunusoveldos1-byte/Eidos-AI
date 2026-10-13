"""Optional floating voice controls; application owns visibility and persistence."""
from PyQt6.QtCore import QEvent, QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QCheckBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .mascot import Mascot, STATE_DESCRIPTIONS
from .voice_orb import VoiceOrb, TITLES, MIC_TITLES


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
    settings_requested = pyqtSignal()
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
        self.mascot = VoiceOrb(220)
        self.mascot.setParent(self)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumHeight(24)
        self.status_label.setMaximumHeight(40)
        self.microphone_label = QLabel(MIC_TITLES['inactive'])
        self.microphone_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.microphone_label.setFixedHeight(20)
        self.start_button = self.mascot
        self.stop_button = QPushButton('Остановить')
        self.pause_button = QPushButton('Отключить микрофон')
        self.open_button = QPushButton('В главное окно')
        self.settings_button = QPushButton('Настройки')
        self.settings_button.clicked.connect(self.settings_requested)
        self.answer_label = QLabel('Последний ответ появится здесь')
        self.answer_label.setWordWrap(True)
        self.answer_label.setTextFormat(Qt.TextFormat.PlainText)
        self.answer_label.setFixedHeight(42)
        self.answer_label.setStyleSheet('color: #A8B7AE; padding: 4px;')
        self.title_bar = QLabel('EIDOS  /  голос')
        self.title_bar.setFixedHeight(24)
        self.title_bar.setToolTip('Перетащите за эту панель')
        self.pin_checkbox = QCheckBox('Поверх окон')
        controls = QGridLayout()
        self.start_button.clicked.connect(self.start_requested)
        for index, name in enumerate(('open',)):
            button = getattr(self, name + '_button')
            button.setAccessibleName(button.text())
            button.clicked.connect(getattr(self, name + '_requested').emit)
            controls.addWidget(button, index // 2, index % 2)
        controls.addWidget(self.settings_button, 0, 1)
        self.stop_button.hide()
        self.pause_button.hide()
        self.pin_checkbox.toggled.connect(self.set_pinned)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(4)
        top = QHBoxLayout()
        top.addWidget(self.title_bar)
        self.collapse_button = QPushButton('Свернуть')
        self.collapse_button.clicked.connect(self.collapse)
        top.addWidget(self.collapse_button)
        layout.addLayout(top)
        self.collapsed = False
        self.badge = MicrophoneBadge(self)

        layout.addWidget(self.mascot, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.microphone_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.answer_label)
        layout.addLayout(controls)
        layout.addWidget(self.pin_checkbox)
        self.setFixedSize(360, 470)
        self.title_bar.installEventFilter(self)
        QApplication.instance().screenRemoved.connect(self._screens_changed)
        QApplication.instance().screenAdded.connect(self._screen_added)
        for screen in QApplication.screens():
            self._screen_added(screen)
        self.set_status('ready', '')
        self.set_microphone('inactive')

    def collapse(self):
        self.collapsed = True
        self.badge.move(self.pos())
        self.hide()
        self.badge.show()

    def expand(self):
        self.collapsed = False
        self.move(self.badge.pos())
        self.badge.hide()
        self.restore_position(self.x(), self.y())
        self.show()

    def set_status(self, state: str, message: str = '') -> None:
        self.mascot.set_state(state)
        self.badge.orb.set_state(state)
        status = TITLES.get(state, 'Обрабатываю')
        self._response_text = 'Ответ: ' + status + ('\n' + message if message else '')
        self._response_message = message
        self._refresh_description()
        self.status_label.setAccessibleName(self.status_label.text())
        self.setAccessibleDescription(self.status_label.text())

    def set_microphone(self, state, error=''):
        self.mascot.set_microphone(state, error)
        self.badge.orb.set_microphone(state, error)
        self.microphone_label.setText(MIC_TITLES[state])
        self.microphone_label.setToolTip(error)
        self.microphone_label.setAccessibleDescription(error)
        self._refresh_description()

    def _refresh_description(self):
        error = self.mascot.microphone_error
        if error:
            short_error = error.split('.')[0]
            if len(short_error) > 46:
                short_error = short_error[:45] + '…'
            text = self._response_text.split('\n')[0] + '\n' + short_error
        else:
            text = self._response_text
        self.status_label.setText(text)
        self.status_label.setToolTip(error or self._response_message)

    def set_microphone_paused(self, paused):
        self.pause_button.setText('Включить микрофон' if paused else 'Отключить микрофон')
        self.pause_button.setToolTip('Включить голосовой ввод' if paused else 'Отключить голосовой ввод; озвучка управляется кругом')

    def set_answer(self, text):
        self.answer_label.setText(text[:160] + ('…' if len(text) > 160 else ''))
        self.answer_label.setToolTip(text)

    def _screen_added(self, screen):
        screen.availableGeometryChanged.connect(self._screens_changed)

    def _screens_changed(self, *args):
        self.restore_position(self.x(), self.y())
        self.position_changed.emit(self.x(), self.y())

    def set_level(self, value: float) -> None:
        if self.mascot.state == 'speaking':
            self.mascot.set_speech_level(value)
        else:
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
        if watched is self.title_bar and self._drag_event(event):
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


class MicrophoneBadge(QWidget):
    def __init__(self, owner):
        super().__init__(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.orb = VoiceOrb(64, self)
        self.setFixedSize(64, 64)
        self.setStyleSheet('background: #151B18;')
        self.orb.clicked.connect(owner.expand)
        self.orb.installEventFilter(self)
        self._press = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self._press = event.globalPosition().toPoint()
            self._origin = self.pos()
        elif event.type() == QEvent.Type.MouseMove and self._press is not None:
            self.move(self._origin + event.globalPosition().toPoint() - self._press)
        elif event.type() == QEvent.Type.MouseButtonRelease and self._press is not None:
            moved = (event.globalPosition().toPoint() - self._press).manhattanLength() > 5
            self._press = None
            if moved:
                self.orb.setDown(False)
                self.owner.position_changed.emit(self.x(), self.y())
                return True
        return super().eventFilter(obj, event)
