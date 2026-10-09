"""Five-page shell; voice engine coordination stays in the existing controller."""
from dataclasses import replace
from datetime import datetime
import logging

from PyQt6.QtCore import QSignalBlocker, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from eidos.core.config import AppConfig, ConfigStore
from eidos.modules.voice.controller import VoiceController
from eidos.modules.voice.recorder import Microphone
from .components import button
from .icons import icon
from .mascot import Mascot
from .pages.home import HomePage
from .pages.voice import VoicePage
from .pages.gestures import GesturesPage
from .pages.translation import TranslationPage
from .pages.settings import SettingsPage
from .sidebar import Sidebar
from .theme import STYLE, install_font

class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore | None = None) -> None:
        super().__init__()
        install_font()
        self.store = store or ConfigStore()
        self.config = self.store.load()
        self._allow_close = False
        self._microphones: list[Microphone] = []
        self._updating = False
        self.current_state = 'idle'
        self.compact = False
        self._normal_geometry = None
        self.setWindowTitle('Eidos')
        self.setWindowIcon(icon('mic', '#2FE09B'))
        self.resize(1200, 800)
        self.setMinimumSize(780, 560)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self.controller = VoiceController(self.store.path.parent / 'models', self)
        self.controller.state_changed.connect(self._state_changed)
        self.controller.transcript.connect(self.voice.recognized.text.setPlainText)
        self.controller.reply.connect(self.voice.answer.text.setPlainText)
        self.controller.log_event.connect(self._log)
        self.controller.devices.connect(self._devices)
        self.controller.devices_error.connect(self._devices_error)
        self.controller.closed.connect(self._closed)
        self.sidebar.selected.connect(self.navigate)
        self.home.navigate_requested.connect(self.navigate)
        self.home.compact_requested.connect(lambda: self.set_compact(True))
        self.return_button.clicked.connect(lambda: self.set_compact(False))
        self.voice.action_requested.connect(self._action)
        self.voice.refresh_requested.connect(self._refresh)
        self.voice.microphone.currentIndexChanged.connect(self._voice_microphone_changed)
        self.voice.speak.toggled.connect(self._voice_speak_changed)
        self.settings.save_requested.connect(self._save_settings)
        self.settings.reset_requested.connect(self._reset_settings)
        self.settings.load(self.config)
        self._apply_preferences()
        self.navigate(0)
        for index in range(5):
            shortcut = QShortcut(QKeySequence(f'Ctrl+{index + 1}'), self)
            shortcut.activated.connect(lambda page=index: self.navigate(page))
        if self.store.warning:
            self._log(self.store.warning)
        self._log('Eidos готов. Микрофон включается только по кнопке. Лимит записи — 120 секунд.')
        QTimer.singleShot(0, self._refresh)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName('shell')
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)
        right = QWidget()
        content = QVBoxLayout(right)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(0)
        self.return_button = button('Вернуться к полному окну', 'monitor')
        self.return_button.hide()
        content.addWidget(self.return_button)
        self.pages = QStackedWidget()
        self.home = HomePage()
        self.voice = VoicePage()
        self.gestures = GesturesPage()
        self.translation = TranslationPage()
        self.settings = SettingsPage()
        for page in (self.home, self.voice, self.gestures, self.translation, self.settings):
            self.pages.addWidget(page)
        content.addWidget(self.pages, 1)
        layout.addWidget(right, 1)

    @pyqtSlot(int)
    def navigate(self, index: int) -> None:
        if not 0 <= index < self.pages.count():
            return
        if self.compact and index != 1:
            self.set_compact(False)
        self.pages.setCurrentIndex(index)
        self.sidebar.activate(index)

    def set_compact(self, enabled: bool) -> None:
        if self.compact == enabled:
            return
        self.compact = enabled
        if enabled:
            self._normal_geometry = self.saveGeometry()
            self.setMinimumSize(480, 560)
            self.sidebar.hide()
            self.return_button.show()
            self.pages.setCurrentIndex(1)
            self.sidebar.activate(1)
            self.resize(560, 720)
        else:
            self.setMinimumSize(780, 560)
            self.sidebar.show()
            self.return_button.hide()
            if self._normal_geometry:
                self.restoreGeometry(self._normal_geometry)

    def _apply_preferences(self) -> None:
        blocker = QSignalBlocker(self.voice.speak)
        self.voice.speak.setChecked(self.config.speak)
        del blocker
        for mascot in self.findChildren(Mascot):
            mascot.set_animations(self.config.mascot_animation)
        target_flag = Qt.WindowType.WindowStaysOnTopHint
        enabled = bool(self.windowFlags() & target_flag)
        if enabled != self.config.always_on_top:
            visible = self.isVisible()
            self.setWindowFlag(target_flag, self.config.always_on_top)
            if visible:
                self.show()

    def _persist(self, config: AppConfig) -> bool:
        try:
            self.store.save(config)
        except (OSError, ValueError):
            self._log('Не удалось сохранить настройки. Проверьте доступ к папке профиля.')
            self.settings.feedback.setText('Не удалось сохранить настройки.')
            return False
        self.config = config
        self._apply_preferences()
        return True

    def _microphone_choice(self, control) -> tuple[int | None, str | None]:
        index = control.currentData()
        if index == -1:
            return self.config.microphone, self.config.microphone_name
        return index, next((mic.name for mic in self._microphones if mic.index == index), None)

    @pyqtSlot()
    def _save_settings(self) -> None:
        if self.controller.active or self.controller.playback.active or self.controller.closing:
            return
        microphone, name = self._microphone_choice(self.settings.microphone)
        config = replace(self.config, microphone=microphone, microphone_name=name,
                         whisper_model=self.settings.model.currentText(),
                         device=self.settings.device.currentData(),
                         speak=self.settings.speak.isChecked(), tts_voice=self.settings.tts_voice.currentData(),
                         always_on_top=self.settings.on_top.isChecked(),
                         mascot_animation=self.settings.animation.isChecked())
        if self._persist(config):
            blocker = QSignalBlocker(self.voice.microphone)
            self.voice.microphone.setCurrentIndex(self.voice.microphone.findData(
                -1 if self.settings.microphone.currentData() == -1 else microphone))
            del blocker
            self.settings.feedback.setText('Настройки сохранены.')
            self._log('Настройки сохранены.')
        self._update_controls()

    @pyqtSlot()
    def _reset_settings(self) -> None:
        response = QMessageBox.question(
            self, 'Сбросить настройки?', 'Вернуть настройки Eidos к значениям по умолчанию?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        if self._persist(AppConfig()):
            self.settings.load(self.config)
            self._select_microphone(self.voice.microphone, self.config)
            self._select_microphone(self.settings.microphone, self.config)
            self.settings.feedback.setText('Настройки сброшены.')
            self._log('Настройки сброшены к значениям по умолчанию.')
        self._update_controls()

    @pyqtSlot(bool)
    def _voice_speak_changed(self, checked: bool) -> None:
        if self._updating:
            return
        if self._persist(replace(self.config, speak=checked)):
            self.settings.speak.setChecked(checked)
        else:
            blocker = QSignalBlocker(self.voice.speak)
            self.voice.speak.setChecked(self.config.speak)
            del blocker

    @pyqtSlot(int)
    def _voice_microphone_changed(self, index: int) -> None:
        if self._updating or self.voice.microphone.currentData() == -1:
            return
        microphone, name = self._microphone_choice(self.voice.microphone)
        if self._persist(replace(self.config, microphone=microphone, microphone_name=name)):
            self._select_microphone(self.settings.microphone, self.config)
        self._update_controls()

    def _select_microphone(self, control, config: AppConfig) -> None:
        blocker = QSignalBlocker(control)
        match = control.findData(config.microphone)
        if match < 0:
            match = control.findData(-1)
        control.setCurrentIndex(max(match, 0))
        del blocker

    @pyqtSlot(object)
    def _devices(self, microphones: list[Microphone]) -> None:
        self._updating = True
        self._microphones = microphones
        selected = None
        if self.config.microphone is not None:
            selected = next((mic for mic in microphones if mic.name == self.config.microphone_name and
                             mic.index == self.config.microphone), None)
            selected = selected or next((mic for mic in microphones if mic.name == self.config.microphone_name), None)
        if selected and selected.index != self.config.microphone:
            self._persist(replace(self.config, microphone=selected.index))
        for control in (self.voice.microphone, self.settings.microphone):
            blocker = QSignalBlocker(control)
            control.clear()
            control.addItem('Микрофон по умолчанию', None)
            for mic in microphones:
                control.addItem(mic.name, mic.index)
            if self.config.microphone is not None:
                if selected:
                    control.setCurrentIndex(control.findData(selected.index))
                else:
                    control.addItem('Сохранённый микрофон недоступен', -1)
                    control.setCurrentIndex(control.count() - 1)
            control.setToolTip(control.currentText())
            del blocker
        self._updating = False
        if not microphones:
            self.voice.operation.setText('Микрофоны не найдены. Подключите устройство и обновите список.')
        elif self.voice.microphone.currentData() == -1:
            self.voice.operation.setText('Сохранённый микрофон недоступен. Выберите другой.')
        self._log(f'Найдено входных устройств: {len(microphones)}.')
        self._update_controls()

    @pyqtSlot(str)
    def _devices_error(self, message: str) -> None:
        self._microphones = []
        self.voice.show_state('error', message)
        self._log(message)
        self._update_controls()

    def _update_controls(self) -> None:
        busy = self.controller.active or self.controller.playback.active
        unavailable = self.controller.closing or self.controller.discovering
        can_start = bool(self._microphones) and self.voice.microphone.currentData() != -1
        self.voice.action_button.setEnabled(not unavailable and not self.controller.cancelling and (busy or can_start))
        for control in (self.voice.microphone, self.voice.speak, self.settings.content):
            control.setEnabled(not busy and not unavailable)
        self.voice.refresh_button.setEnabled(not busy and not unavailable)
        self.settings.save_button.setEnabled(not busy and not unavailable)
        self.settings.reset_button.setEnabled(not busy and not unavailable)

    @pyqtSlot(str, str)
    def _state_changed(self, state: str, message: str) -> None:
        self.current_state = state
        visual_state = 'error' if state == 'idle' and message.startswith('Ошибка') else state
        self.voice.show_state(visual_state, message)
        self.home.status.setText('●  ' + message)
        self.sidebar.logo.set_state(self.voice.mascot.state)
        self._update_controls()

    @pyqtSlot()
    def _action(self) -> None:
        if not self.voice.action_button.isEnabled():
            return
        if self.controller.active or self.controller.playback.active:
            self.controller.stop()
            self.voice.action_button.setEnabled(False)
            return
        self.voice.recognized.text.clear()
        self.voice.answer.text.clear()
        self.controller.start(self.config)

    @pyqtSlot()
    def _refresh(self) -> None:
        self.controller.refresh_devices()
        self._update_controls()

    @pyqtSlot(str)
    def _log(self, message: str) -> None:
        self.voice.journal.appendPlainText(f'{datetime.now():%H:%M:%S}  {message}')
        logging.getLogger('eidos').info(message)

    @pyqtSlot()
    def _closed(self) -> None:
        self._allow_close = True
        QTimer.singleShot(0, self.close)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
        else:
            event.ignore()
            self.controller.shutdown()
