"""Application-owned tray, microphone handoff and shared speech surfaces."""
from dataclasses import replace
from collections import deque
from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from .icons import icon
from .mascot import Mascot
from eidos.modules.voice.speech import SpeechQueue
from eidos.modules.voice.wake import WakeController
import time


class BackgroundControls(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.paused = self.pending_voice = self.closing = False
        self._capture_visible = False
        self._capture_active = False
        self._pending_audio = None
        self._pending_speech = deque()
        self._quiet_until = 0.
        self._listening_count = 0
        self.listen_enabled = False
        self._greeting_pending = self._greeted = False
        self._response_completed = False
        self._microphones = {'manual': ('inactive', ''), 'wake': ('inactive', '')}
        self.floating = window.placement.desktop
        self.floating.start_requested.connect(self.voice_action)
        self.floating.stop_requested.connect(self.stop_action)
        self.floating.pause_requested.connect(self.toggle_pause)
        self.floating.open_requested.connect(self.open_window)
        self.floating.settings_requested.connect(lambda: (self.open_window(), window.navigate(4)))
        self.floating.position_changed.connect(self._position)
        self.speech = SpeechQueue(window, window.controller.playback)
        self.speech.state_changed.connect(self._speech_state)
        self.speech.closed.connect(window._closed)
        self.wake = WakeController(window, window.agent_service.secrets)
        self.wake.activated.connect(self._wake_triggered)
        self.wake.command_ready.connect(self._wake_audio)
        self.wake.level.connect(self.level)
        self.wake.microphone_changed.connect(lambda state, text: self._microphone_changed('wake', state, text))
        self.wake.status.connect(self._wake_status)
        self.wake.stopped.connect(self._try_voice)
        self.wake.stopped.connect(window._closed)
        window.controller.level.connect(self.level)
        window.controller.microphone_changed.connect(lambda state, text: self._microphone_changed('manual', state, text))
        window.controller.devices_error.connect(lambda text: self._microphone_changed('manual', 'error', text))
        window.controller.playback.level.connect(self.speech_level)
        window.controller.playback.finished.connect(self._audio_ended)
        window.controller.reply.connect(self.floating.set_answer)
        window.controller.reply.connect(self._mark_response_completed)
        self.tray = QSystemTrayIcon(window.windowIcon(), window)
        menu = QMenu(window)
        menu.addAction('Открыть Eidos', self.open_window)
        menu.addAction('Показать персонажа', window.placement.show_character)
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
        self.window.placement.apply(config)
        for mascot in self.mascots():
            mascot.set_animations(self.window._motion_enabled())
        QApplication.instance().setQuitOnLastWindowClosed(not (self.tray_available() and (config.close_to_tray or config.start_in_tray)))
        self.wake.configure(config)
        self.wake.pause(self.paused)
        self.floating.set_microphone_paused(self.paused)
        self._refresh_microphone()
        self._tick()

    def mascots(self):
        window = self.window
        return (window.character, window.voice.mascot)

    def _mark_response_completed(self, text):
        self._response_completed = bool(text.strip())

    def celebrate(self):
        self._response_completed = True
        if not self.speech.active and not self._pending_speech:
            self._response_completed = False
            self.window.character.celebrate()

    def status(self, state, message):
        mapping = {'idle': 'ready', 'starting': 'listening', 'recording': 'listening',
                   'loading': 'thinking', 'transcribing': 'thinking', 'synthesizing': 'thinking',
                   'playing': 'speaking', 'running': 'acting'}
        visual = mapping.get(state, state)
        if visual not in ('ready', 'listening', 'thinking', 'acting', 'speaking', 'error', 'paused'):
            visual = 'thinking'
        for mascot in self.mascots():
            mascot.set_state(visual)
        response = {'ready': 'Ответ: готов', 'listening': 'Ответ: ожидаю команду',
                    'speaking': 'Ответ: говорю', 'paused': 'Ответ: на паузе',
                    'error': 'Ответ: ошибка'}.get(visual, 'Ответ: обрабатываю')
        self.window.voice.response_status.setText(response)
        self.floating.set_status(visual, message)
        self._refresh_microphone()
        self.tray.setToolTip(('Eidos — ' + message)[:120])
        if visual == 'error':
            self._response_completed = False
        elif visual == 'ready' and self._response_completed:
            self.celebrate()

    def _microphone_changed(self, source, state, message):
        self._microphones[source] = (state, message)
        if source == 'manual' and state == 'enabled' and self.listen_enabled and not self._greeted:
            self._greeted = True
            self._greeting_pending = True
            self.window.controller.cancel()
        if source == 'manual' and state == 'error':
            self.listen_enabled = False
            self._greeting_pending = False
        if (state == 'waiting' and not self.paused and not self.window.controller.active
                and not self.window.controller.playback.active and not self.speech.active
                and not self.window.agent_controller.active):
            self.status('ready', 'Ожидаю команду после «Эйдос»')
            self.window.voice.set_operation('Ожидаю команду после «Эйдос»')
        self._refresh_microphone()

    def _refresh_microphone(self):
        states = tuple(self._microphones.values())
        state, message = ('off', '') if self.paused else next(
            ((kind, text) for kind in ('recording', 'waiting', 'enabled', 'error')
             for actual, text in states if kind == actual), ('inactive' if self.listen_enabled else 'off', ''))
        self.window.voice.set_microphone(state, message)
        self.floating.set_microphone(state, message)
        self.window.character.set_microphone(state, message)
        self.window.mascot_stage.status_label.setText(
            self.window.voice.title.text() + ' · Перетащите персонажа / меню правой кнопкой')
        action = 'Выключить голосовой режим' if self.listen_enabled else 'Включить голосовой режим'
        for button in (self.window.voice.action_button, self.floating.start_button):
            button.setText(action)
            button.setAccessibleName(action)
            button.setToolTip(action + '\nПробел / Enter при фокусе')

    def level(self, value):
        self.window.voice.input_level.setText(f'Входной уровень: {min(100, round(value * 1000))}%')
        for mascot in self.mascots():
            mascot.set_level(value)
        self.floating.set_level(value)

    def speech_level(self, value):
        self.window.voice.mascot.set_speech_level(value)
        self.floating.mascot.set_speech_level(value)
        self.window.character.set_speech_level(value)

    def _wake_status(self, message):
        self.window.settings.wake_status.setText(message)
        if message.startswith('Слово активации недоступно') and self._microphones['wake'][0] != 'error':
            self.status('error', message)

    def _tick(self):
        window = self.window
        busy = (window.controller.active or window.controller.playback.active or self.speech.active
                or window.agent_controller.active or self.pending_voice or self.closing
                or self._pending_speech or self._capture_active or window.translation.is_running or time.monotonic() < self._quiet_until)
        self.wake.set_busy(busy or self.listen_enabled)
        self._flush_speech()
        self._try_voice()
        if self._greeting_pending and not window.controller.active:
            self._greeting_pending = False
            greeting = 'Привет! Я Эйдос. Слушаю вас'
            window.voice.answer.text.setPlainText(greeting)
            self.floating.set_answer(greeting)
            if window.config.speak:
                self.speak(greeting, full=True)
        elif (self.listen_enabled and not self.paused and not busy and not self.pending_voice
              and not self.wake.is_running and not window.controller.discovering):
            self.pending_voice = True
            self._try_voice()

    def _flush_speech(self):
        if self.closing or self.wake.is_running:
            return
        while self._pending_speech:
            text, config = self._pending_speech.popleft()
            if not self.speech.enqueue(text, config):
                self.window.voice.set_operation('Очередь озвучки заполнена. Текст доступен в интерфейсе.')

    def voice_action(self):
        window = self.window
        if self.closing:
            return
        if self.listen_enabled:
            self.listen_enabled = False
            self._greeting_pending = False
            self.paused = True
            self.wake.pause(True)
            self.stop_action()
            self.status('ready', 'Голосовой режим выключен')
        else:
            self.listen_enabled = True
            self.paused = False
            self._greeted = False
            self.wake.pause(False)
            self.pending_voice = True
            self.wake.set_busy(True)
            self._try_voice()
        self.window._update_controls()
        self._refresh_microphone()

    def _try_voice(self):
        window = self.window
        if self.closing or not self.pending_voice or self.paused:
            return
        if self.wake.is_running or self.speech.active or self._pending_speech or window.controller.active or window.controller.discovering:
            return
        self.pending_voice = False
        if not self.listen_enabled:
            window.voice.recognized.text.clear()
            window.voice.answer.text.clear()
        if self._pending_audio is not None:
            audio, recording_id = self._pending_audio
            self._pending_audio = None
            window.controller.start_audio(replace(window.config, speak=False), audio, recording_id)
        else:
            config = replace(window.config, speak=False, continuous_listening=self.listen_enabled)
            window.controller.start(config)
            from eidos.modules.voice.personality import listening_reply
            self._listening_count += 1
            window.voice.set_operation(listening_reply(window.config.communication_style,
                window.agent_service.settings.name, use_name=self._listening_count % 4 == 0))

    def _wake_triggered(self):
        if self.paused or self.closing:
            return
        self.status('recording', 'Слушаю команду после «Эйдос»')

    def _wake_audio(self, audio, recording_id):
        if self.paused or self.closing:
            return
        self._pending_audio = (audio, recording_id)
        self.pending_voice = True
        self._try_voice()

    def stop_speech(self):
        self._pending_speech.clear()
        was_active = self.window.controller.playback.active or self.speech.active
        self.speech.stop()
        if self.window.controller.playback.active:
            self.window.controller.stop()
        if was_active:
            self._audio_ended()

    def _audio_ended(self):
        self._quiet_until = time.monotonic() + .7

    def stop_action(self):
        self._response_completed = False
        self.pending_voice = False
        self._pending_audio = None
        self.wake.set_busy(True)
        self.stop_speech()
        if self.window.controller.active:
            self.window.controller.cancel()
        if self.window.agent_controller.active:
            self.window.agent_controller.cancel()
        if self.window.translation._selecting:
            self.window.translation._cancel_selection()
        elif self.window.translation.is_running:
            self.window.translation.cancel_translation()

    def _speech_state(self, state, message):
        self.status(state, message)
        self.window.voice.set_operation(message)
        if state == 'idle':
            self._audio_ended()
        self.window._update_controls()
        self.window._agent_controls()
        self._tick()

    def speak(self, text, *, full=False, config=None):
        if not self.closing and text.strip():
            if len(text) > self.speech.MAX_CHARACTERS or len(self._pending_speech) >= 8:
                self.window.voice.set_operation('Ответ слишком длинный для очереди речи. Текст доступен в интерфейсе.')
                return False
            self.wake.set_busy(True)
            snapshot = config or self.window.config
            self._pending_speech.append((text, replace(snapshot, voice_response_brief=False) if full else snapshot))
            self._flush_speech()
            return True
        return False

    def toggle_pause(self):
        self.paused = not self.paused
        self.pending_voice = False
        self._pending_audio = None
        self.wake.pause(self.paused)
        self.pause_action.setText('Возобновить прослушивание' if self.paused else 'Приостановить прослушивание')
        self.window.voice.mute_button.setText('Включить микрофон' if self.paused else 'Отключить микрофон')
        self.window.voice.mute_button.setToolTip('Разрешить голосовой ввод' if self.paused else
            'Отключить голосовой ввод и активацию. Озвучка управляется отдельно.')
        self.floating.set_microphone_paused(self.paused)
        if self.paused:
            if self.window.current_state in ('starting', 'recording'):
                self.window.controller.cancel()
        player = self.window.controller.playback
        if player.active:
            self.status('paused' if player.paused else 'playing', 'Озвучка на паузе' if player.paused else 'Говорю')
        elif self.paused:
            self.status('ready', 'Микрофон выключен')
        elif not self.window.controller.active and not self.speech.active:
            self.status('ready', 'Готов к голосовому вводу')
        self.window._update_controls()
        self._refresh_microphone()

    def open_window(self):
        if self.closing:
            return
        if self.window.isMaximized():
            self.window.showMaximized()
        else:
            self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _position(self, x, y):
        if not self.closing:
            self.window._persist(replace(self.window.config, floating_x=x, floating_y=y))

    def capture_started(self):
        self._capture_active = True
        self.wake.set_busy(True)
        self.window.placement.set_capture(True)

    def capture_finished(self):
        self._capture_active = False
        if not self.closing:
            self.window.placement.set_capture(False)
        self._capture_visible = False

    def shutdown(self):
        if self.closing:
            return
        self.closing = True
        self.pending_voice = False
        self.timer.stop()
        self.tray.hide()
        self.window.placement.shutdown()
        self.wake.shutdown()
        self.speech.shutdown()
