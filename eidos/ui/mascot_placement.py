"""One character widget, reparented between a reserved stage and a desktop host.

Only presentation lives here. Microphone, playback and agent remain application
owned. Positions use Qt logical coordinates, including negative monitor origins.
"""
from dataclasses import replace
from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLabel, QMenu, QWidget
from .floating import clamp_position
from .mascot import Mascot, STATE_DESCRIPTIONS
from .voice_orb import MIC_TITLES


class InteractiveMascot(Mascot):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__(150)
        self.setFixedSize(150, 150)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip('Клик — голосовой режим · Перетаскивание — перемещение · Правая кнопка — меню')
        self.microphone_state = 'off'
        self.microphone_error = ''
        self.speech_level = 0.
        self.placement = None
        self._press = None
        self._dragged = False

    def setText(self, text):
        self.setAccessibleDescription(text)

    def set_microphone(self, state, error=''):
        self.microphone_state, self.microphone_error = state, error
        self._sync_animation()
        self.update()

    def _sync_animation(self):
        super()._sync_animation()
        if getattr(self, 'microphone_state', '') == 'error' and self.state == 'ready':
            self.visual_timer.stop()
            self.offset = 0.

    def current_frame(self):
        if self.microphone_state == 'error' and self.state == 'ready':
            from .mascot import emotion_frames
            return emotion_frames()['error'][0]
        return super().current_frame()

    def set_speech_level(self, value):
        self.speech_level = value

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.placement:
            self._press = event.globalPosition().toPoint()
            self._dragged = False
            self._origin = self.placement.position()
            self.setFocus()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None:
            delta = event.globalPosition().toPoint() - self._press
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self._dragged = True
            if self._dragged:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.placement.move_character(self._origin + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            delta = event.globalPosition().toPoint() - self._press
            dragged = self._dragged or delta.manhattanLength() >= QApplication.startDragDistance()
            self._press = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if dragged:
                self.placement.move_character(self._origin + delta)
                self.placement.save_position()
            else:
                self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        if self.placement:
            menu = self.placement.menu()
            menu.exec(event.globalPos())
            menu.deleteLater()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
        elif self.placement and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = {Qt.Key.Key_Left: QPoint(-10, 0), Qt.Key.Key_Right: QPoint(10, 0),
                     Qt.Key.Key_Up: QPoint(0, -10), Qt.Key.Key_Down: QPoint(0, 10)}[event.key()]
            self.placement.move_character(self.placement.position() + delta)
            self.placement.save_position()
        else:
            super().keyPressEvent(event)


class MascotStage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(184)
        self.setObjectName('mascotStage')
        self.status_label = QLabel('Персонаж · клик — голос · правая кнопка — меню', self)
        self.status_label.setGeometry(18, 2, 700, 24)
        self.status_label.setStyleSheet('color: #82958A; font-size: 12px;')


class DesktopMascot(QWidget):
    """Transparent host. It never constructs its own Mascot or audio objects."""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    open_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    position_changed = pyqtSignal(int, int)

    def __init__(self, placement):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.placement = placement
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle('Eidos — персонаж')
        self.setFixedSize(220, 230)
        self.mascot = self.start_button = placement.character
        self.answer_label = QLabel(self)
        self.answer_label.setGeometry(4, 2, 212, 64)
        self.answer_label.setWordWrap(True)
        self.answer_label.setTextFormat(Qt.TextFormat.PlainText)
        self.answer_label.setStyleSheet('background: #1C3026; color: #E7F4EC; border: 1px solid #355746; border-radius: 12px; padding: 8px; font: 12px "Inter";')
        self.answer_label.hide()
        self.bubble_timer = QTimer(self)
        self.bubble_timer.setSingleShot(True)
        self.bubble_timer.timeout.connect(self.answer_label.hide)
        # These labels are state metadata for accessibility, not a second panel.
        self.status_label, self.microphone_label = QLabel(self), QLabel(self)
        self.status_label.hide()
        self.microphone_label.hide()
        self._response_text = 'Ответ: готов'
        self._response_message = self._mic_error = ''

    def set_status(self, state, message=''):
        self._response_text = 'Ответ: ' + STATE_DESCRIPTIONS.get(state, state)
        self._response_message = message
        self._refresh_description()
        self.setAccessibleDescription(self.status_label.text())

    def set_microphone(self, state, error=''):
        self.microphone_label.setText(MIC_TITLES[state])
        self.microphone_label.setToolTip(error)
        self.status_label.setToolTip(error)
        self._mic_error = error
        self._refresh_description()

    def _refresh_description(self):
        message = self._mic_error or self._response_message
        self.status_label.setText(self._response_text + ('\n' + message if message else ''))
        self.mascot.setAccessibleDescription(self.microphone_label.text() + '\n' + self.status_label.text())

    def set_microphone_paused(self, paused):
        pass  # Menu derives its current action from BackgroundControls.

    def set_answer(self, text):
        self.answer_label.setText(text[:115] + ('…' if len(text) > 115 else ''))
        self.answer_label.setToolTip(text)
        self.answer_label.setVisible(bool(text.strip()))
        self.bubble_timer.start(7000)

    def set_level(self, value):
        self.mascot.set_level(value)

    def restore_position(self, x, y):
        self.move(clamp_position(QPoint(x, y), self.size(),
                                 [s.availableGeometry() for s in QApplication.screens()]))

    def set_pinned(self, enabled):
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) == bool(enabled):
            return
        visible, position = self.isVisible(), self.pos()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        self.move(position)
        if visible:
            self.show()


class MascotPlacement(QObject):
    def __init__(self, window, character, stage):
        super().__init__(window)
        self.window, self.character, self.stage = window, character, stage
        self.mode = 'app'
        self.hidden = False
        self.capture_active = False
        character.placement = self
        self.desktop = DesktopMascot(self)
        self.stage.installEventFilter(self)
        app = QApplication.instance()
        app.screenAdded.connect(self._watch_screen)
        app.screenRemoved.connect(self._screen_changed)
        for screen in app.screens():
            self._watch_screen(screen)
        self._mount(stage, QPoint(20, 30))

    def _watch_screen(self, screen):
        screen.availableGeometryChanged.connect(self._screen_changed)

    def _screen_changed(self, *args):
        self.desktop.restore_position(self.desktop.x(), self.desktop.y())
        if self.mode == 'desktop':
            self.save_position()

    def _mount(self, parent, position):
        tick, offset = self.character._tick, self.character.offset
        self.character.setParent(parent)
        self.character.move(position)
        self.character._tick, self.character._offset = tick, offset
        self.character.show()

    def apply(self, config):
        target = 'desktop' if config.floating_enabled else 'app'
        self.hidden = config.mascot_hidden
        if target != self.mode:
            self._transfer(target)
        self.desktop.set_pinned(config.floating_pinned)
        if target == 'desktop' and not self.character._press:
            self.desktop.restore_position(config.floating_x, config.floating_y)
        elif target == 'app' and not self.character._press:
            self.move_character(QPoint(config.mascot_app_x, 30))
        self._visibility()

    def _transfer(self, mode):
        self.mode = mode
        if mode == 'desktop':
            self._mount(self.desktop, QPoint(35, 72))
        else:
            self._mount(self.stage, QPoint(self.window.config.mascot_app_x, 30))
        self.desktop.hide()

    def _visibility(self):
        visible = not self.hidden and not self.capture_active and not self.window._closing
        self.desktop.setVisible(visible and self.mode == 'desktop')
        self.character.setVisible(visible)
        self.stage.setVisible(self.mode == 'app' and not self.hidden and self.window.pages.currentIndex() != 0)

    def to_desktop(self):
        self.window._persist(replace(self.window.config, floating_enabled=True, mascot_hidden=False))

    def to_app(self):
        self.window._persist(replace(self.window.config, floating_enabled=False, mascot_hidden=False))

    def hide_character(self):
        self.window._persist(replace(self.window.config, mascot_hidden=True))

    def show_character(self):
        self.window._persist(replace(self.window.config, mascot_hidden=False))

    def position(self):
        return self.desktop.pos() if self.mode == 'desktop' else self.character.pos()

    def move_character(self, target):
        if self.mode == 'desktop':
            self.desktop.move(target)
        else:
            self.character.move(max(0, min(target.x(), self.stage.width() - self.character.width())), 30)

    def save_position(self):
        if self.mode == 'desktop':
            self.desktop.restore_position(self.desktop.x(), self.desktop.y())
            config = replace(self.window.config, floating_x=self.desktop.x(), floating_y=self.desktop.y())
        else:
            config = replace(self.window.config, mascot_app_x=self.character.x())
        self.window._persist(config)

    def set_capture(self, active):
        self.capture_active = active
        self._visibility()

    def menu(self):
        menu = QMenu(self.character)
        menu.setStyleSheet('QMenu { background: #15231B; color: #F2F6F3; padding: 6px; } QMenu::item:selected { background: #285139; }')
        background = self.window.background
        menu.addAction('Открыть Eidos', background.open_window)
        menu.addAction('Микрофон выкл' if background.listen_enabled else 'Микрофон вкл', background.voice_action)
        menu.addAction('Остановить озвучку', background.stop_speech)
        menu.addAction('Остановить задачу', background.stop_action)
        menu.addSeparator()
        menu.addAction('Вернуть в приложение' if self.mode == 'desktop' else 'На рабочий стол',
                       self.to_app if self.mode == 'desktop' else self.to_desktop)
        pin = menu.addAction('Поверх окон')
        pin.setCheckable(True)
        pin.setChecked(self.window.config.floating_pinned)
        pin.toggled.connect(lambda enabled: self.window._persist(replace(self.window.config, floating_pinned=enabled)))
        menu.addAction('Скрыть персонажа', self.hide_character)
        return menu

    def eventFilter(self, watched, event):
        if watched is self.stage and event.type() == QEvent.Type.Resize and self.mode == 'app':
            self.move_character(self.character.pos())
            self.stage.status_label.setFixedWidth(max(0, self.stage.width() - 36))
        return super().eventFilter(watched, event)

    def shutdown(self):
        self.desktop.bubble_timer.stop()
        self.desktop.hide()
        self.character.hide()
        # Give ownership back to MainWindow before it is destroyed.
        if self.character.parentWidget() is self.desktop:
            self.character.setParent(self.stage)
        self.desktop.close()
