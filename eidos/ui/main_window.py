"""Original five pages and assistant workspace; controllers own background work."""
from dataclasses import replace
from datetime import datetime
import logging

from PyQt6.QtCore import QEvent, QEasingCurve, QLocale, QPropertyAnimation, QSignalBlocker, QTimer, Qt, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QStackedWidget, QVBoxLayout
from eidos.ui.localized import QMainWindow, QMenu, QMessageBox, QWidget

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
from .pages.workspace import reorganize
from .mascot_placement import InteractiveMascot, MascotStage, MascotPlacement
from .voice_orb import VoiceOrb
from .sidebar import Sidebar, SidebarHost
from .theme import ASSETS, STYLE, install_font
from .motion import system_reduced_motion
from eidos.agent.service import AgentService
from .pages.assistant import AssistantPage
from .assistant_bindings import AssistantBindings
from .hotkeys import TranslationHotkeys, GestureEmergencyHotkey
from eidos.core.shortcuts import ACTIONS


class MainWindow(AssistantBindings, QMainWindow):
    # Qt threads finish asynchronously. A hidden/closed window must remain
    # alive even if its last external Python reference is released meanwhile.
    _closing_windows = set()
    def __init__(self, store: ConfigStore | None = None) -> None:
        super().__init__()
        from .localized import install_native_translator
        install_native_translator()
        install_font()
        self.store = store or ConfigStore()
        self.config = self.store.load()
        from eidos.core.i18n import set_language
        set_language(self.config.ui_language)
        from eidos.core.startup import WindowsStartup
        self.startup = WindowsStartup()
        self._startup_error = ''
        try:
            self.config = replace(self.config, startup_enabled=self.startup.enabled())
        except (OSError, ValueError):
            self._startup_error = 'Не удалось проверить автозапуск Windows.'
        self.agent_service = AgentService(self.store.path.parent)
        self._allow_close = False
        self._closing = False
        self._microphones: list[Microphone] = []
        self._updating = False
        self._device_inventory_error = False
        self.current_state = 'idle'
        self.compact = False
        self._normal_geometry = None
        self.setWindowTitle('Eidos')
        self.setWindowIcon(QIcon(str(ASSETS / 'eidos-home.png')))
        self.resize(1200, 800)
        self.setMinimumSize(780, 560)
        self.setStyleSheet(STYLE)
        self._build_ui()
        from .toast import Toasts
        self.toasts = Toasts(self)
        self.assistant.feedback.notification.connect(self.toasts.show)
        self.gestures.notice.connect(self.toasts.show)
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
        self.home.capture_requested.connect(lambda: self.translation.start_capture())
        self.home.compact_requested.connect(lambda: self.set_compact(True))
        self.home.app_requested.connect(self._home_apps)
        self.return_button.clicked.connect(lambda: self.set_compact(False))
        self.voice.action_requested.connect(self._action)
        self.voice.refresh_requested.connect(self._refresh)
        self.voice.microphone.currentIndexChanged.connect(self._voice_microphone_changed)
        self.voice.speak.toggled.connect(self._voice_speak_changed)
        self.settings.save_requested.connect(self._save_settings)
        self.settings.reset_requested.connect(self._reset_settings)
        voice_blocker = QSignalBlocker(self.voice.speak)
        self.settings.load(self.config)
        self.settings.startup_status.setText(self._startup_error or
            ('Автозапуск зарегистрирован' if self.config.startup_enabled else 'Автозапуск выключен'))
        del voice_blocker
        self.translation.load_preferences(self.config)
        self.translation.preferences_changed.connect(self._translation_preferences_changed)
        self.hotkeys = TranslationHotkeys(self)
        self.hotkeys.activated.connect(self._translation_hotkey)
        self.hotkeys.status_changed.connect(self.settings.hotkeys_status.setText)
        self.hotkeys.status_changed.connect(lambda message: self._update_hotkey_hints())
        self.hotkeys.configure(self.config)
        self.gesture_hotkey = GestureEmergencyHotkey(self)
        self.gesture_hotkey.configure(self.config)
        self.gestures.bind_hotkey(self.gesture_hotkey)
        self.gestures.load(self.config)
        self.gestures.preferences_changed.connect(self._gesture_preferences_changed)
        self.gestures.stopped.connect(self._closed)
        self._apply_preferences()
        self._set_sidebar(self.config.sidebar_collapsed, animate=False)
        self.menu_shortcut = QShortcut(QKeySequence('Ctrl+B'), self)
        self.menu_shortcut.setAutoRepeat(False)
        self.menu_shortcut.activated.connect(self.toggle_sidebar)
        QApplication.instance().applicationStateChanged.connect(self._sync_home_motion)
        self.navigate(0)
        for number, page_id in enumerate(self.sidebar.page_ids, 1):
            shortcut = QShortcut(QKeySequence(f'Ctrl+{number}'), self)
            shortcut.activated.connect(lambda page=page_id: self.navigate(page))
        if self.store.warning:
            self._log(self.store.warning)
        self._log(f'Eidos готов. Активация включается отдельно. Лимит команды — {self.config.voice_max_seconds} секунд.')
        self._init_agent(show_onboarding=False)
        self.controller.transcript.connect(lambda text: self.assistant.history.appendPlainText('Вы\n' + text + '\n') if text.strip() else None)
        self.controller.reply.connect(lambda text: self.assistant.history.appendPlainText('Eidos\n' + text + '\n') if text.strip() else None)
        from .background import BackgroundControls
        self.background = BackgroundControls(self)
        self.character.clicked.connect(self.background.voice_action)
        self.settings.character_button.clicked.connect(self.placement.show_character)
        self.voice.stop_requested.connect(self.background.stop_action)
        self.voice.mute_requested.connect(self.background.toggle_pause)
        self.voice.compact_requested.connect(self._show_voice_widget)
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
        self.translation.explain_requested.connect(self._explain_screen_text)
        self.translation.original.text.textChanged.connect(lambda: setattr(self.agent_service, 'screen_text', None))
        self.gestures.status_changed.connect(lambda text: setattr(self.agent_service, 'camera_status', text))
        self.gestures.status_changed.connect(self._camera_indicator)
        self._camera_indicator(self.gestures.camera_status.source_text())
        self.translation.translated.text.textChanged.connect(self._translation_voice_result)
        QTimer.singleShot(0, self._refresh)

    def _explain_screen_text(self, text):
        if not text:
            self.translation.feedback.setText('Сначала выделите область или введите текст.')
            return
        self.agent_service.screen_text = text[:12000]
        self.navigate(3)
        if self._start_agent_task('screen_explain', text[:12000]):
            self.assistant.history.appendPlainText('Вы\nОбъясни текст выбранной области:\n' + text[:12000] + '\n')

    def _camera_indicator(self, text):
        self.home.set_camera_status(text)
        self.camera_indicator.setText(text)
        self.camera_indicator.hide()

    def _home_apps(self):
        if hasattr(self, 'app_menu'):
            self.app_menu.hide()
            self.app_menu.deleteLater()
        self.app_menu = QMenu(self)
        self.app_menu.addAction('Блокнот', lambda: self._start_agent_task('tool', ('open_notepad', {})))
        for name in sorted(self.agent_service.settings.approved_apps):
            self.app_menu.addAction(name, lambda checked=False, app=name: self._start_agent_task('tool', ('open_app', {'name': app})))
        self.app_menu.addSeparator()
        self.app_menu.addAction('Добавить приложение…', self._add_app)
        self.app_menu.popup(self.home.app_button.mapToGlobal(self.home.app_button.rect().bottomLeft()))

    def toggle_sidebar(self):
        if self.compact:
            self.set_compact(False)
            if not self.config.sidebar_collapsed:
                return
        collapsed = not self.config.sidebar_collapsed
        try:
            config = replace(self.config, sidebar_collapsed=collapsed)
            self.store.save(config)
        except (OSError, ValueError):
            self.menu_button.setChecked(self.config.sidebar_collapsed)
            self.assistant.feedback.setText('Не удалось сохранить состояние меню.')
            return
        self.config = config
        self._set_sidebar(collapsed)

    def _set_sidebar(self, collapsed, animate=True):
        self.sidebar_animation.stop()
        self.menu_button.setToolTip('Показать меню' if collapsed else 'Скрыть меню')
        self.menu_button.setAccessibleName(self.menu_button.toolTip())
        self.menu_button.setChecked(collapsed)
        self.menu_button.setIcon(icon('chevron-right' if collapsed else 'chevron-left', '#25E6A1'))
        # Keep the same control available while its sidebar slides out of view.
        self.menu_button.setParent(self.workspace)
        self._position_menu_button()
        self.menu_button.show()
        self.menu_button.raise_()
        for page in (self.pages.widget(i) for i in range(self.pages.count())):
            if hasattr(page, 'header'):
                page.header.setContentsMargins(34 if collapsed else 0, 0, 0, 0)
        self.sidebar.show()
        if animate and self._motion_enabled() and self.isVisible():
            self.sidebar_animation.setStartValue(self.sidebar_host.width())
            self.sidebar_animation.setEndValue(0 if collapsed else 240)
            self.sidebar_animation.start()
        else:
            self.sidebar_host.panelWidth = 0 if collapsed else 240
            self._finish_sidebar()

    def _position_menu_button(self, *args):
        if self.menu_button.parentWidget() is self.workspace:
            self.menu_button.move(max(12, self.sidebar_host.width() - 48), 24)

    def _finish_sidebar(self):
        expanded = self.sidebar_host.width() > 0
        self.sidebar.setVisible(expanded)
        self.menu_button.setParent(self.sidebar if expanded else self.workspace)
        self.menu_button.move(self.sidebar.width() - 48 if expanded else 12, 24)
        self.menu_button.show()
        self.menu_button.raise_()

    def _motion_enabled(self):
        return self.config.mascot_animation and not self.config.reduce_animations and not system_reduced_motion()

    def _sync_home_motion(self, *args):
        if hasattr(self, 'home'):
            self.home.set_animations(self._motion_enabled())
            self.sidebar.set_animations(self._motion_enabled() and not self.isMinimized())
            self.voice.mascot.set_animations(self._motion_enabled() and not self.isMinimized())
        if hasattr(self, 'character'):
            self.character.set_animations(self._motion_enabled() and not self.isMinimized())

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.WindowStateChange, QEvent.Type.ActivationChange):
            self._sync_home_motion()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName('shell')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.menu_button = button('', 'chevron-left')
        self.menu_button.setObjectName('menuToggle')
        self.menu_button.setFixedSize(34, 34)
        self.menu_button.setCheckable(True)
        self.menu_button.clicked.connect(self.toggle_sidebar)
        self.workspace = QWidget()
        outer.addWidget(self.workspace, 1)
        layout = QHBoxLayout(self.workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar()
        self.sidebar_host = SidebarHost(self.sidebar)
        layout.addWidget(self.sidebar_host)
        self.sidebar_animation = QPropertyAnimation(self.sidebar_host, b'panelWidth', self)
        self.sidebar_animation.setDuration(280)
        self.sidebar_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.sidebar_animation.valueChanged.connect(self._position_menu_button)
        self.sidebar_animation.finished.connect(self._finish_sidebar)
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
        self.home.attach_voice(self.voice)
        self.voice.mascot.presentation_changed.connect(self._home_voice_status)
        self.gestures = GesturesPage(self.store.path.parent / 'models' / 'vision')
        self.translation = TranslationPage()
        self.settings = SettingsPage()
        for page in (self.home, self.voice, self.gestures, self.translation, self.settings):
            self.pages.addWidget(page)
        self.assistant = AssistantPage(self.agent_service)
        self.assistant.setParent(self)
        self.assistant.hide()
        # Stable service IDs; removed destinations never host a visible page.
        self.pages.addWidget(QWidget())
        reorganize(self)
        self.pages.addWidget(self.tools)
        self.assistant.feedback.setStyleSheet('color: #A8B7AE; padding: 0px 28px;')
        content.addWidget(self.assistant.feedback)
        from .components import label
        self.camera_indicator = label('', 'muted')
        self.camera_indicator.hide()
        content.addWidget(self.camera_indicator)
        content.addWidget(self.pages, 1)
        self.mascot_stage = MascotStage()
        content.addWidget(self.mascot_stage)
        self.character = InteractiveMascot()
        self.placement = MascotPlacement(self, self.character, self.mascot_stage)
        # Compatibility references point to the same character, never copies.
        self.assistant.mascot = self.sidebar.logo = self.character
        layout.addWidget(right, 1)

    def show_startup(self):
        if self.config.start_in_tray and self.background.tray_available():
            self.hide()
        else:
            self.showMaximized()

    @pyqtSlot(int)
    def navigate(self, index: int) -> None:
        if index in (5, 7):
            return
        # Keep old shortcuts and service entry points stable after moving voice.
        if index == 1:
            index = 0
        if not 0 <= index < self.pages.count():
            return
        if self.compact and index != 0:
            self.set_compact(False)
        self.pages.setCurrentIndex(index)
        self.sidebar.activate(index)
        self.placement._visibility()
        self.home.sync_motion()
        self.camera_indicator.hide()

    def set_compact(self, enabled: bool) -> None:
        if self.compact == enabled:
            return
        self.compact = enabled
        if enabled:
            self._normal_geometry = self.saveGeometry()
            self.setMinimumSize(480, 560)
            self.sidebar_animation.stop()
            self.sidebar_host.panelWidth = 0
            self.sidebar.hide()
            self._finish_sidebar()
            self.menu_button.setIcon(icon('chevron-right', '#25E6A1'))
            self.menu_button.setToolTip('Показать меню')
            self.menu_button.setAccessibleName('Показать меню')
            self.voice.header.setContentsMargins(34, 0, 0, 0)
            self.return_button.show()
            self.pages.setCurrentIndex(0)
            self.sidebar.activate(0)
            self.resize(560, 720)
        else:
            self.setMinimumSize(780, 560)
            self._set_sidebar(self.config.sidebar_collapsed, animate=False)
            self.return_button.hide()
            if self._normal_geometry:
                self.restoreGeometry(self._normal_geometry)

    def _apply_preferences(self) -> None:
        self.setLocale(QLocale(self.config.ui_language))
        from eidos.core.i18n import set_language
        set_language(self.config.ui_language)
        from .theme import style_for
        self.setStyleSheet(style_for(self.config.theme, self.config.accent_color))
        # The home illustration and custom painters use the original dark
        # palette. Keep their text/background together when the shell is light.
        self.home.setStyleSheet(STYLE if self.config.theme == 'light' else '')
        from PyQt6.QtWidgets import QLabel
        for image in self.findChildren(QLabel):
            symbol = image.property('headingIcon')
            if symbol:
                image.setPixmap(icon(symbol, '#15291F' if self.config.theme == 'light' else '#F2F6F3').pixmap(25, 25))
        for control in self.sidebar.buttons:
            control.apply_theme(self.config.theme, self.config.accent_color)
        if hasattr(self, 'agent_controller'):
            self._refresh_skills()
        self._update_processing_info()
        self._update_hotkey_hints()
        if hasattr(self, 'background'):
            self.background.apply()
        blocker = QSignalBlocker(self.voice.speak)
        self.voice.speak.setChecked(self.config.speak)
        del blocker
        for mascot in self.findChildren(Mascot) + self.findChildren(VoiceOrb):
            mascot.set_animations(self._motion_enabled())
        self.home.set_animations(self._motion_enabled())
        self.sidebar.set_animations(self._motion_enabled())
        if not self.compact and self.menu_button.isChecked() != self.config.sidebar_collapsed:
            self._set_sidebar(self.config.sidebar_collapsed, animate=False)
        target_flag = Qt.WindowType.WindowStaysOnTopHint
        enabled = bool(self.windowFlags() & target_flag)
        if enabled != self.config.always_on_top:
            visible = self.isVisible()
            self.setWindowFlag(target_flag, self.config.always_on_top)
            if visible:
                self.show()

    def _update_processing_info(self):
        settings = self.agent_service.settings
        model = ('Модель: Ollama на выбранном сервере ' + settings.ollama_url if settings.provider == 'ollama'
            else 'Модель: Gemini — запрос и выбранный контекст отправляются в Google' if settings.provider == 'gemini'
            else 'Модель: OpenAI — запрос и выбранный контекст отправляются внешнему провайдеру')
        tts = 'Озвучка: Windows SAPI локально' if self.config.tts_provider == 'sapi' else 'Озвучка: Edge онлайн, отправляется текст ответа'
        translation = 'Перевод: Google онлайн, отправляется только текст' if self.config.translation_provider else 'Внешний перевод выключен'
        self.settings.processing_info.setText(model + '.\nOCR и STT: локально. ' + tts + '.\n' + translation + '. Камера и распознавание жестов: локально, видео не сохраняется и не отправляется.')

    def _persist(self, config: AppConfig) -> bool:
        try:
            config.validate()
        except ValueError as exc:
            self.settings.feedback.setText(str(exc))
            return False
        if not self.hotkeys.configure(config):
            self.settings.feedback.setText(self.hotkeys.message)
            return False
        if not self.gesture_hotkey.configure(config):
            self.gestures.emergency_stop()
            self.hotkeys.configure(self.config)
            self.settings.feedback.setText(self.gesture_hotkey.message)
            return False
        try:
            if config.startup_enabled != self.config.startup_enabled:
                self.startup.configure(config.startup_enabled)
            self.store.save(config)
        except (OSError, ValueError):
            if config.startup_enabled != self.config.startup_enabled:
                try:
                    self.startup.configure(self.config.startup_enabled)
                except (OSError, ValueError):
                    self.settings.startup_status.setText('Не удалось восстановить автозапуск. Проверьте настройки Windows.')
            self.hotkeys.configure(self.config)
            self.gesture_hotkey.configure(self.config)
            self._log('Не удалось сохранить настройки. Проверьте доступ к папке профиля.')
            self.settings.feedback.setText('Не удалось сохранить настройки.')
            return False
        gesture_changed = any(getattr(self.config, name) != getattr(config, name)
                              for name in config.__dataclass_fields__ if name.startswith('gesture_'))
        self.config = config
        self.settings.startup_status.setText('Автозапуск зарегистрирован' if config.startup_enabled else 'Автозапуск выключен')
        if gesture_changed:
            self.gestures.emergency_stop()
            self.gestures.load(config)
            self.gestures.service.configure(self.gestures.settings(), False)
        self._apply_preferences()
        return True

    def _gesture_preferences_changed(self, values):
        self.gestures.emergency_stop()
        if self._persist(replace(self.config, **values)):
            self.gestures.load(self.config)
            self.gestures.service.configure(self.gestures.settings(), False)
            self.gestures.preferences_saved(True, 'Параметры жестов сохранены. Управление включается отдельно.')
        else:
            self.gestures.preferences_saved(False, self.settings.feedback.text())

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
        defaults = replace(AppConfig(), mascot_hidden=self.config.mascot_hidden,
                           mascot_app_x=self.config.mascot_app_x,
                           floating_enabled=self.config.floating_enabled,
                           floating_pinned=self.config.floating_pinned,
                           floating_x=self.config.floating_x, floating_y=self.config.floating_y)
        if self._persist(defaults):
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
            if self._device_inventory_error and hasattr(self, 'background'):
                self._device_inventory_error = False
                self.background._microphone_changed('manual', 'inactive', '')
                self.voice.mascot.set_state('ready')
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
                control.addRawItem(mic.name, mic.index)
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
            self.voice.set_operation('Микрофоны не найдены. Подключите устройство и обновите список.')
            self._device_inventory_error = True
            if hasattr(self, 'background'):
                self.background._microphone_changed('manual', 'error', 'Микрофон не найден')
        elif self._device_inventory_error:
            self._device_inventory_error = False
            if hasattr(self, 'background'):
                self.background._microphone_changed('manual', 'inactive', '')
            self.voice.mascot.set_state('ready')
        if self.voice.microphone.currentData() == -1:
            self.voice.set_operation('Сохранённый микрофон недоступен. Выберите другой.')
            self._device_inventory_error = True
            if hasattr(self, 'background'):
                self.background._microphone_changed('manual', 'error', 'Выбранный микрофон не найден')
        self._log(f'Найдено входных устройств: {len(microphones)}.')
        self._update_controls()

    @pyqtSlot(str)
    def _devices_error(self, message: str) -> None:
        self._device_inventory_error = True
        self._microphones = []
        self.voice.show_state('error', message)
        self._log(message)
        self._update_controls()

    def _update_controls(self) -> None:
        busy = self.controller.active or self.controller.playback.active
        if hasattr(self, 'background'):
            busy = busy or self.background.speech.active or bool(self.background._pending_speech)
        agent_busy = hasattr(self, 'agent_controller') and self.agent_controller.active
        unavailable = self.controller.closing or self.controller.discovering
        can_start = bool(self._microphones) and self.voice.microphone.currentData() != -1
        muted = hasattr(self, 'background') and self.background.paused
        recording = self.controller.active and self.current_state in ('starting', 'recording')
        waking = hasattr(self, 'background') and self.background.wake.capturing
        self.voice.action_button.setEnabled(not self.controller.closing and
            (hasattr(self, 'background') and self.background.listen_enabled or
             not unavailable and not busy and not agent_busy and self.voice.mascot.ui_state == 'error' or
             not unavailable and not busy and not agent_busy and can_start))
        if hasattr(self, 'background'):
            self.background.floating.start_button.setEnabled(self.voice.action_button.isEnabled())
        for control in (self.voice.microphone, self.voice.speak, self.settings.content):
            control.setEnabled(not busy and not agent_busy and not unavailable)
        self.voice.refresh_button.setEnabled(not busy and not unavailable)
        self.settings.save_button.setEnabled(not busy and not unavailable)
        self.settings.reset_button.setEnabled(not busy and not unavailable)

    @pyqtSlot(str, str)
    def _state_changed(self, state: str, message: str) -> None:
        self.current_state = state
        visual_state = 'error' if state == 'idle' and message.startswith('Ошибка') else state
        if visual_state == 'error' and state == 'idle' and self.voice.mascot.state == 'error':
            # Worker completion must retain the actionable original service error.
            message = self.voice.mascot.message or message
        self.voice.show_state(visual_state, message)
        self.home.status.setText('●  ' + {'idle': 'Готов помочь', 'recording': 'Слушаю', 'loading': 'Подготовка', 'transcribing': 'Распознаю', 'thinking': 'Думаю', 'speaking': 'Говорю', 'error': 'Нужна проверка'}.get(visual_state, 'Работаю'))
        self.home.status.setToolTip(message)
        self.sidebar.logo.set_state(self.voice.mascot.state)
        if hasattr(self, 'background'):
            if state == 'idle' and self.background.speech.active:
                paused = self.controller.playback.paused
                self.background.status('paused' if paused else 'playing' if self.controller.playback.active else 'synthesizing',
                                       'Озвучка на паузе' if paused else 'Говорю…' if self.controller.playback.active else 'Подготовка речи…')
            else:
                self.background.status(visual_state, message)
        self._update_controls()
        if hasattr(self, 'agent_controller'):
            self._agent_controls()

    def _home_voice_status(self):
        orb = self.voice.mascot
        if orb.ui_state == 'error' or orb.state == 'error':
            self.home.status.setText('●  Нужна проверка')
            self.home.status.setToolTip(orb.copy()[0])
        elif orb.state in ('thinking', 'acting', 'speaking'):
            self.home.status.setText('●  ' + {'thinking': 'Думаю', 'acting': 'Выполняю', 'speaking': 'Говорю'}[orb.state])
        elif orb.ui_state == 'active':
            self.home.status.setText('●  Слушаю')
        elif orb.ui_state == 'sleep':
            self.home.status.setText('●  Спит')
        elif orb.state == 'ready':
            self.home.status.setText('●  Готов помочь')

    @pyqtSlot()
    def _action(self) -> None:
        if not self.voice.action_button.isEnabled():
            return
        if hasattr(self, 'background'):
            if self.voice.mascot.ui_state == 'error' and not self._microphones:
                self._refresh()
                return
            if self.voice.mascot.ui_state == 'active' and not self.background.listen_enabled:
                self.background.stop_voice_input()
                return
            if self.voice.mascot.ui_state == 'off' and self.background.listen_enabled:
                self.background.stop_voice_input()
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
        # Shutdown can still deliver worker log signals. Keep the file log,
        # but do not update QTextDocument/layouts on a closing window.
        if not self._closing:
            self.voice.journal.appendPlainText(f'{datetime.now():%H:%M:%S}  {message}')
        logging.getLogger('eidos').info(message)

    @pyqtSlot()
    def _closed(self) -> None:
        if not self._closing:
            return
        if hasattr(self, 'background') and (self.background.speech.is_running or self.background.wake.is_running
                                           or (self.background.latch and self.background.latch.isRunning())):
            return
        if hasattr(self, 'agent_controller') and self.agent_controller.thread.isRunning():
            return
        if self.controller.thread.isRunning() or self.translation.is_running:
            return
        if self.gestures.is_running:
            return
        if hasattr(self, 'session_monitor') and self.session_monitor.isRunning():
            return
        self._allow_close = True
        QTimer.singleShot(0, self._finish_close)

    def _finish_close(self):
        try:
            self.close()
        finally:
            self._closing_windows.discard(self)

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
                self.translation.start_capture()
        elif action == 'repeat':
            if not self.translation.is_running and not self.translation._selecting:
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
            if hasattr(self, 'session_monitor'):
                self.session_monitor.stop()
            if hasattr(self, 'desktop_ui'):
                self.desktop_ui.hide_power()
            if hasattr(self, 'toasts'):
                self.toasts.close()
            self._closing_windows.add(self)
            if hasattr(self, 'background'):
                self.background.shutdown()
            self.hotkeys.shutdown()
            self.gesture_hotkey.shutdown()
            self.gestures.shutdown(final=True)
            self.translation.shutdown()
            self._shutdown_agent()
            self.controller.shutdown()

    def request_exit(self):
        self._closing = True
        self.close()

    def nativeEvent(self, event_type, message):
        import os
        if (os.name == 'nt' and bytes(event_type) in (b'windows_generic_MSG', b'windows_dispatcher_MSG')
                and hasattr(self, 'session_monitor')):
            try:
                import ctypes
                from ctypes.wintypes import MSG
                msg = MSG.from_address(int(message))
                if msg.message in (0x11, 0x16) or (msg.message == 0x218 and msg.wParam == 4):
                    self.session_monitor.snapshot()
            except (ValueError, TypeError, OSError):
                pass
        # This observer never consumes an event. Calling the Qt base virtual
        # here crashes the Windows PyQt trampoline while showing the HWND.
        # False lets Qt perform its normal platform processing after return.
        return False, 0

    def _voice_reply_speech(self, text):
        full = self.controller.worker.full_reply
        if (self.config.speak or full) and not self._closing:
            self.background.speak(text, full=full)

    def _voice_cycle_finished(self):
        if hasattr(self.controller.worker.recorder, 'end_of_speech'):
            self.controller.worker.recorder.end_of_speech = False

    def _speech_sample(self):
        if self.controller.active or self.agent_controller.active or self._closing:
            return
        from dataclasses import replace
        self.background.stop_speech()
        self.background.speak('Привет! Я Эйдос. Помогу с делами и отвечу на вопросы.',
                              config=replace(self.config, **self.settings.background_values(),
                                             tts_voice=self.settings.tts_voice.currentData()))

    def _show_voice_widget(self):
        if self._persist(replace(self.config, floating_enabled=True, mascot_hidden=False)):
            self.settings.floating_enabled.setChecked(True)
            self.background.floating.show()
            self.background.floating.raise_()

    def _translation_voice_result(self):
        text = self.translation.translated.text.toPlainText().strip()
        if text and hasattr(self, 'background'):
            self.voice.answer.text.setPlainText(text)
            self.background.floating.set_answer(text)

    def _load_profile_choices(self):
        profiles = self.agent_service.profiles.selection
        self.settings.profile.clear()
        self.settings.profile.addItems(profiles.names)
        self.settings.profile.setCurrentText(profiles.active)

    def _switch_profile(self, name):
        if not name or self.controller.active or self.agent_controller.active or self._closing:
            self.settings.feedback.setText('Дождитесь завершения задачи перед сменой профиля.')
            return
        if name == self.agent_service.profiles.selection.active:
            return
        try:
            if hasattr(self, '_onboarding'):
                try:
                    if self._onboarding.isVisible():
                        self._onboarding.reject()  # Skip belongs to the profile that opened the form.
                except RuntimeError:
                    pass
            self.background.stop_action()
            self.agent_service.activate_profile(name)
            self._load_profile_choices()
            settings = self.agent_service.settings
            form = self.assistant.profile
            form.name.setText(settings.name)
            form.tasks.setPlainText(settings.tasks)
            form.language.setCurrentText(settings.language)
            form.memory.setChecked(settings.memory_enabled)
            self.assistant.memory_enabled.setChecked(settings.memory_enabled)
            for i in range(form.professions.count()):
                item = form.professions.item(i)
                item.setCheckState(Qt.CheckState.Checked if item.text() in settings.professions else Qt.CheckState.Unchecked)
            self.assistant.history.clear()
            self.voice.recognized.text.clear()
            self.voice.answer.text.clear()
            self.background.floating.set_answer('')
            self.assistant.incognito.setChecked(False)
            self._update_grants()
            ui = self.assistant
            ui.provider.setCurrentIndex(ui.provider.findData(settings.provider))
            ui.model_name.setText(settings.model)
            ui.cloud_model.setText(settings.cloud_model)
            ui.gemini_model.setText(settings.gemini_model)
            ui.gemini_key.clear()
            ui.ollama_url.setText(settings.ollama_url)
            ui.context_size.setValue(settings.context_size)
            ui.search_provider.setCurrentIndex(ui.search_provider.findData(settings.search_provider))
            for kind in ('telegram', 'discord'):
                ui.bot_enabled[kind].setChecked(getattr(settings, kind + '_enabled'))
                ui.bot_users[kind].setText(', '.join(getattr(settings, kind + '_users')))
                ui.bot_channels[kind].setText(', '.join(getattr(settings, kind + '_channels')))
            for capability, control in ui.remote_checks.items():
                control.setChecked(capability in settings.remote_permissions)
            for control in ui.secrets_edits.values():
                control.clear()
            self._refresh_memory()
            self._refresh_calendar()
            self._refresh_apps()
            self._profile_hints()
            self.settings.feedback.setText('Выбран профиль: ' + name)
            if not settings.onboarding_done:
                self._show_onboarding()
        except (ValueError, RuntimeError, OSError) as exc:
            self.settings.feedback.setText(str(exc))

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
