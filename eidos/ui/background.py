"""Application-owned tray, microphone handoff and shared speech surfaces."""
from dataclasses import replace
from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from .icons import icon
from .floating import FloatingMascot
from eidos.modules.voice.speech import SpeechQueue
from eidos.modules.voice.wake import WakeController


class BackgroundControls(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.paused = self.pending_voice = self.closing = False
        self._capture_visible = False
        self.floating = FloatingMascot()
        self.floating.start_requested.connect(self.voice_action)
        self.floating.stop_requested.connect(self.stop_action)
        self.floating.pause_requested.connect(self.toggle_pause)
        self.floating.open_requested.connect(self.open_window)
        self.floating.position_changed.connect(self._position)
        self.floating.pin_checkbox.toggled.connect(lambda value: window._persist(replace(window.config, floating_pinned=value)))
        self.speech = SpeechQueue(window, window.controller.playback)
        self.speech.state_changed.connect(self._speech_state)
        self.speech.closed.connect(window._closed)
        self.wake = WakeController(window, window.agent_service.secrets)
        self.wake.activated.connect(self._wake_triggered)
        self.wake.level.connect(self.level)
        self.wake.status.connect(self._wake_status)
        self.wake.stopped.connect(self._try_voice)
        self.wake.stopped.connect(window._closed)
        window.controller.level.connect(self.level)
        self.tray = QSystemTrayIcon(icon('mic', '#2FE09B'), window)
        menu = QMenu(window)
        menu.addAction('Открыть Eidos', self.open_window)
        menu.addAction('Начать голосовой ввод', self.voice_action)
        self.pause_action = menu.addAction('Приостановить прослушивание', self.toggle_pause)
        menu.addAction('Остановить озвучку', self.stop_speech)
        menu.addSeparator()
        menu.addAction('Выход', window.request_exit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.open_window() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if self.tray_available():
            self.tray.show()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.apply()

    def tray_available(self):
        return QSystemTrayIcon.isSystemTrayAvailable()

    def apply(self):
        config = self.window.config
        self.floating.set_pinned(config.floating_pinned)
        if not self.floating.isVisible():
            self.floating.restore_position(config.floating_x, config.floating_y)
        self.floating.setVisible(config.floating_enabled and not self.closing and not self.window.translation._selecting)
        for mascot in self.mascots():
            mascot.set_animations(config.mascot_animation and not config.reduce_animations)
        QApplication.instance().setQuitOnLastWindowClosed(not (self.tray_available() and config.close_to_tray))
        self.wake.configure(config)
        self.wake.pause(self.paused)
        self._tick()

    def mascots(self):
        window = self.window
        return (window.voice.mascot, window.assistant.mascot, window.sidebar.logo, self.floating.mascot)

    def status(self, state, message):
        mapping = {'idle': 'ready', 'starting': 'listening', 'recording': 'listening',
                   'loading': 'thinking', 'transcribing': 'thinking', 'synthesizing': 'thinking',
                   'playing': 'speaking', 'running': 'acting'}
        visual = mapping.get(state, state)
        if visual not in ('ready', 'listening', 'thinking', 'acting', 'speaking', 'error', 'paused'):
            visual = 'thinking'
        if self.paused and visual == 'ready':
            visual, message = 'paused', 'Прослушивание отключено'
        for mascot in self.mascots():
            mascot.set_state(visual)
        self.floating.set_status(visual, message)
        self.tray.setToolTip(('Eidos — ' + message)[:120])

    def level(self, value):
        for mascot in self.mascots():
            mascot.set_level(value)
        self.floating.set_level(value)

    def _wake_status(self, message):
        self.window.settings.wake_status.setText(message)
        if message.startswith('Ожидаю слово') and not self.paused and not self.closing:
            self.status('listening', message + ' Микрофон включён.')
        elif message.startswith('Слово активации недоступно'):
            self.status('error', message)

    def _tick(self):
        window = self.window
        busy = (window.controller.active or window.controller.playback.active or self.speech.active
                or window.agent_controller.active or self.pending_voice or self.closing)
        self.wake.set_busy(busy)
        self._try_voice()

    def voice_action(self):
        window = self.window
        if self.closing:
            return
        if self.paused:
            window.settings.wake_status.setText('Прослушивание отключено. Возобновите его в меню трея или виджете.')
            return
        if window.controller.active:
            window.controller.stop()
            return
        if window.agent_controller.active:
            window.agent_controller.cancel()
            return
        if window.controller.discovering:
            return
        self.stop_speech()
        self.pending_voice = True
        self.wake.set_busy(True)
        self._try_voice()

    def _try_voice(self):
        window = self.window
        if self.closing or not self.pending_voice or self.paused:
            return
        if self.wake.is_running or self.speech.active or window.controller.active or window.controller.discovering:
            return
        self.pending_voice = False
        window.voice.recognized.text.clear()
        window.voice.answer.text.clear()
        window.controller.start(replace(window.config, speak=False))

    def _wake_triggered(self):
        if self.paused or self.closing:
            return
        self.window.controller.worker.recorder.end_of_speech = True
        self.voice_action()

    def stop_speech(self):
        self.speech.stop()
        if self.window.controller.playback.active:
            self.window.controller.stop()

    def stop_action(self):
        self.stop_speech()
        if self.window.controller.active:
            self.window.controller.stop()
        if self.window.agent_controller.active:
            self.window.agent_controller.cancel()

    def _speech_state(self, state, message):
        self.status(state, message)
        self.window.voice.operation.setText(message)
        self.window._update_controls()
        self.window._agent_controls()
        self._tick()

    def speak(self, text):
        if not self.closing and text.strip():
            self.wake.set_busy(True)
            return self.speech.enqueue(text, self.window.config)
        return False

    def toggle_pause(self):
        self.paused = not self.paused
        self.pending_voice = False
        self.wake.pause(self.paused)
        self.pause_action.setText('Возобновить прослушивание' if self.paused else 'Приостановить прослушивание')
        if self.paused:
            self.window.controller.worker.cancel_event.set()
            self.window.controller.worker.stop_event.set()
            self.status('paused', 'Прослушивание отключено')
        else:
            self.status('ready', 'Готов к голосовому вводу')

    def open_window(self):
        if self.closing:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _position(self, x, y):
        if not self.closing:
            self.window._persist(replace(self.window.config, floating_x=x, floating_y=y))

    def capture_started(self):
        self._capture_visible = self.floating.isVisible()
        self.floating.hide()

    def capture_finished(self):
        if self._capture_visible and not self.closing:
            self.floating.show()
        self._capture_visible = False

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.pending_voice = False
        self.timer.stop()
        self.tray.hide()
        self.floating.hide()
        self.wake.shutdown()
        self.speech.shutdown()
