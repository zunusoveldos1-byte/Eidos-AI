"""Original five pages and assistant workspace; controllers own background work."""
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
from eidos.agent.service import AgentService
from .pages.assistant import AssistantPage
from .assistant_bindings import AssistantBindings
from .hotkeys import TranslationHotkeys
from eidos.core.shortcuts import ACTIONS

class MainWindow(AssistantBindings, QMainWindow):
    def __init__(self, store: ConfigStore | None = None) -> None:
        super().__init__()
        install_font()
        self.store = store or ConfigStore()
        self.config = self.store.load()
        self.agent_service = AgentService(self.store.path.parent)
        self._allow_close = False
        self._closing = False
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
        self.translation.stopped.connect(self._translation_stopped)
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
        self.translation.load_preferences(self.config)
        self.translation.preferences_changed.connect(self._translation_preferences_changed)
        self.hotkeys = TranslationHotkeys(self)
        self.hotkeys.activated.connect(self._translation_hotkey)
        self.hotkeys.status_changed.connect(self.settings.hotkeys_status.setText)
        self.hotkeys.status_changed.connect(lambda message: self._update_hotkey_hints())
        self.hotkeys.configure(self.config)
        self._apply_preferences()
        self.navigate(0)
        for index in range(self.pages.count()):
            shortcut = QShortcut(QKeySequence(f'Ctrl+{index + 1}'), self)
            shortcut.activated.connect(lambda page=index: self.navigate(page))
        if self.store.warning:
            self._log(self.store.warning)
        self._log('Eidos готов. Микрофон включается только по кнопке. Лимит записи — 120 секунд.')
        self._init_agent(show_onboarding=store is None)
        from .background import BackgroundControls
        self.background = BackgroundControls(self)
        self.controller.reply.connect(self._voice_reply_speech)
        self.controller.worker.finished.connect(self._voice_cycle_finished)
        self.settings.sample_requested.connect(self._speech_sample)
        self.settings.stop_speech_requested.connect(self.background.stop_speech)
        self.settings.wake_secret_requested.connect(self._save_wake_secret)
        self.settings.voices_requested.connect(self.background.speech.refresh_voices)
        self.background.speech.voices_ready.connect(self.settings.load_sapi_voices)
        self.background.speech.voices_error.connect(self.settings.feedback.setText)
        self.translation.capture_started.connect(self.background.capture_started)
        self.translation.capture_finished.connect(self.background.capture_finished)
        self.translation.speak_requested.connect(self.background.speak)
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
        self.assistant = AssistantPage(self.agent_service)
        self.pages.addWidget(self.assistant)
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
        self._update_hotkey_hints()
        if hasattr(self, 'background'):
            self.background.apply()
        blocker = QSignalBlocker(self.voice.speak)
        self.voice.speak.setChecked(self.config.speak)
        del blocker
        for mascot in self.findChildren(Mascot):
            mascot.set_animations(self.config.mascot_animation and not self.config.reduce_animations)
        target_flag = Qt.WindowType.WindowStaysOnTopHint
        enabled = bool(self.windowFlags() & target_flag)
        if enabled != self.config.always_on_top:
            visible = self.isVisible()
            self.setWindowFlag(target_flag, self.config.always_on_top)
            if visible:
                self.show()

    def _persist(self, config: AppConfig) -> bool:
        try:
            config.validate()
        except ValueError as exc:
            self.settings.feedback.setText(str(exc))
            return False
        if not self.hotkeys.configure(config):
            self.settings.feedback.setText(self.hotkeys.message)
            return False
        try:
            self.store.save(config)
        except (OSError, ValueError):
            self.hotkeys.configure(self.config)
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
                         mascot_animation=self.settings.animation.isChecked(),
                         translation_hotkeys_enabled=self.settings.hotkeys_enabled.isChecked(),
                         **self.settings.background_values(),
                         translation_capture_hotkey=self.settings.capture_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                         translation_repeat_hotkey=self.settings.repeat_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                         translation_dismiss_hotkey=self.settings.dismiss_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText))
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
            self.translation.load_preferences(self.config)
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

    @pyqtSlot(str, str, bool)
    def _translation_preferences_changed(self, source, target, overlay):
        config = replace(self.config, translation_source_language=source,
                         translation_target_language=target, translation_show_overlay=overlay)
        if not self._persist(config):
            self.translation.load_preferences(self.config)
            self.translation.feedback.setText('Не удалось сохранить языки. Проверьте доступ к настройкам.')

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
        if hasattr(self, 'background'):
            busy = busy or self.background.speech.active
        agent_busy = hasattr(self, 'agent_controller') and self.agent_controller.active
        unavailable = self.controller.closing or self.controller.discovering
        can_start = bool(self._microphones) and self.voice.microphone.currentData() != -1
        self.voice.action_button.setEnabled(not agent_busy and not unavailable and not self.controller.cancelling and (busy or can_start))
        for control in (self.voice.microphone, self.voice.speak, self.settings.content):
            control.setEnabled(not busy and not agent_busy and not unavailable)
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
        if hasattr(self, 'background'):
            if state == 'idle' and self.background.speech.active:
                self.background.status('playing' if self.controller.playback.active else 'synthesizing',
                                       'Говорю…' if self.controller.playback.active else 'Подготовка речи…')
            else:
                self.background.status(visual_state, message)
        self._update_controls()
        if hasattr(self, 'agent_controller'):
            self._agent_controls()

    @pyqtSlot()
    def _action(self) -> None:
        if not self.voice.action_button.isEnabled():
            return
        if hasattr(self, 'background'):
            self.background.voice_action()
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
        if not self._closing:
            return
        if hasattr(self, 'background') and (self.background.speech.is_running or self.background.wake.is_running):
            return
        if hasattr(self, 'agent_controller') and self.agent_controller.thread.isRunning():
            return
        if self.controller.thread.isRunning() or self.translation.is_running:
            return
        self._allow_close = True
        QTimer.singleShot(0, self.close)

    def _translation_stopped(self) -> None:
        if self._closing:
            self._closed()

    def _update_hotkey_hints(self):
        controls = {'capture': self.translation.select_button, 'repeat': self.translation.refresh_button,
                    'dismiss': self.translation.remove_button, 'voice': self.voice.action_button}
        active = set(self.hotkeys.actions.values())
        hints = []
        for action, (field, title) in ACTIONS.items():
            text = getattr(self.config, field)
            controls[action].setToolTip(f'{title}: {text}' if action in active else title)
            if action in active:
                hints.append(f'{title}: {text}')
        self.translation.hotkey_hint.setText(' · '.join(hints) if hints else 'Горячие клавиши можно настроить в разделе «Настройки».')

    @pyqtSlot(str)
    def _translation_hotkey(self, action):
        if self._closing:
            return
        if action == 'voice':
            if hasattr(self, 'background'):
                self.background.voice_action()
            return
        if action == 'capture':
            if not self.translation.is_running and not self.translation._selecting:
                self.navigate(3)
                self.translation.start_capture()
        elif action == 'repeat':
            if not self.translation.is_running and not self.translation._selecting:
                self.navigate(3)
                self.translation.refresh_capture()
        elif action == 'dismiss':
            if self.translation._selecting:
                self.translation._cancel_selection()
            elif self.translation.is_running:
                self.translation.cancel_translation()
            else:
                self.translation.dismiss_overlay()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().quit()
        else:
            event.ignore()
            if (not self._closing and self.config.close_to_tray and hasattr(self, 'background')
                    and self.background.tray_available()):
                self.hide()
                return
            self._closing = True
            if hasattr(self, 'background'):
                self.background.shutdown()
            self.hotkeys.shutdown()
            self.translation.shutdown()
            self._shutdown_agent()
            self.controller.shutdown()

    def request_exit(self):
        self._closing = True
        self.close()

    def _voice_reply_speech(self, text):
        if self.config.speak and not self._closing:
            self.background.speak(text)

    def _voice_cycle_finished(self):
        if hasattr(self.controller.worker.recorder, 'end_of_speech'):
            self.controller.worker.recorder.end_of_speech = False

    def _speech_sample(self):
        if self.controller.active or self.agent_controller.active or self._closing:
            return
        from dataclasses import replace
        self.background.stop_speech()
        self.background.speech.enqueue('Привет! Я Эйдос. Помогу с делами и отвечу на вопросы.',
                                       replace(self.config, **self.settings.background_values(),
                                               tts_voice=self.settings.tts_voice.currentData()))

    def _save_wake_secret(self, value):
        try:
            if value.strip():
                self.agent_service.secrets.set('porcupine_access_key', value)
            else:
                self.agent_service.secrets.delete('porcupine_access_key')
            self.settings.wake_access_key.clear()
            self.agent_service.memory.secret_values = self.agent_service.secrets.values()
            self.settings.wake_status.setText('Ключ сохранён отдельно от проекта.' if value.strip() else 'Ключ удалён.')
            self.background.wake.configure(self.config)
        except Exception:
            self.settings.wake_status.setText('Не удалось изменить ключ в Windows Credential Manager.')
