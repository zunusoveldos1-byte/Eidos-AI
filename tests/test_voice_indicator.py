"""Microphone status must follow capture, independently of reply playback."""
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
import sys

import numpy as np
import pytest
from PyQt6.QtCore import QAbstractAnimation
from PyQt6.QtTest import QTest

from test_ui import app, wait_until
from eidos.core.config import AppConfig, ConfigStore
from eidos.modules.voice.worker import VoiceWorker


@pytest.mark.parametrize('failure', [False, True])
def test_indicator_follows_actual_stream_start_and_close(monkeypatch, tmp_path, failure):
    states = []
    class Stream:
        active = True
        def __init__(self, **kwargs):
            self.callback = kwargs['callback']
        def start(self):
            assert not any(s in ('enabled', 'recording') for s, _ in states)
            if failure:
                raise OSError('device removed')
            self.callback(np.ones((1600, 1), dtype=np.float32) * .08, 1600, None, False)
            worker.stop_event.set()
        def abort(self): pass
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(
        InputStream=Stream, query_devices=lambda *_: {'default_samplerate': 16000},
        check_input_settings=lambda **_: None))
    class STT:
        def transcribe(self, *args):
            raise ValueError('Не удалось разобрать речь')
    worker = VoiceWorker(stt=STT())
    worker.microphone_changed.connect(lambda state, text: states.append((state, text)))
    worker.run_cycle(replace(AppConfig(), speak=False), tmp_path)
    if failure:
        assert not any(s in ('enabled', 'recording') for s, _ in states)
        assert states[-1][0] == 'error' and 'микрофон' in states[-1][1].lower()
    else:
        assert any(s == 'enabled' for s, _ in states)
        assert states[-1] == ('inactive', '')  # STT errors are not microphone errors.


def test_starting_is_not_successful_listening(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window._state_changed('starting', 'Открытие микрофона…')
        assert window.voice.mascot.microphone_state == 'off'
        assert window.background.floating.mascot.microphone_state == 'off'
        assert 'Прослушивание включено' not in window.voice.title.text()
        assert 'включён' not in window.voice.mute_button.text()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_real_mic_status_shared_and_error_survives_idle(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        floating = window.background.floating
        for state, title in [('enabled', 'Прослушивание включено'),
                             ('recording', 'Слушаю вас'),
                             ('error', 'Ошибка микрофона')]:
            window.controller.microphone_changed.emit(state, 'Проверьте подключение устройства' if state == 'error' else '')
            assert window.voice.mascot.microphone_state == floating.mascot.microphone_state == state
            assert window.voice.title.text() == floating.microphone_label.text() == title
        window._state_changed('idle', 'Ошибка. Можно повторить запись')
        assert floating.mascot.microphone_state == 'error'
        assert 'ошибка' in window.voice.response_status.text().lower()
        assert 'ошибка' in floating.status_label.text().lower()
        assert 'подключение' in floating.microphone_label.toolTip()
        assert not floating.mascot.visual_timer.isActive()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_mute_is_immediate_and_does_not_pause_reply(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        floating = window.background.floating
        window.controller.microphone_changed.emit('recording', '')
        window.background.toggle_pause()
        window.controller.microphone_changed.emit('enabled', '')  # Late capture event after mute.
        assert floating.microphone_label.text() == window.voice.title.text() == 'Микрофон выключен'
        assert floating.mascot.microphone_state == 'off'
        assert not window.controller.playback.paused
        window.background.status('paused', 'Озвучка на паузе')
        assert floating.mascot.microphone_state == 'off'
        assert 'паузе' in floating.status_label.text()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_waiting_only_after_wake_stream_opens_and_stops(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        background = window.background
        background._wake_status('Ожидаю слово активации…')
        assert window.voice.mascot.microphone_state == 'off'  # Text alone cannot assert capture.
        background.wake.microphone_changed.emit('waiting', '')
        assert window.voice.title.text() == background.floating.microphone_label.text() == 'Жду: „Эйдос“'
        background.wake.microphone_changed.emit('inactive', '')
        assert window.voice.mascot.microphone_state == 'off'
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_disable_decorations_keeps_mic_identity_and_stops_all_motion(app):
    from eidos.ui.voice_orb import VoiceOrb
    orb = VoiceOrb()
    orb.show()
    try:
        orb.set_microphone('waiting', '')
        QTest.qWait(80)
        assert orb.pulse.state() == QAbstractAnimation.State.Running
        orb.set_animations(False)
        assert not orb.visual_timer.isActive()
        assert orb.transition.state() == QAbstractAnimation.State.Stopped
        assert orb.pulse.state() == QAbstractAnimation.State.Stopped
        assert orb.microphone_state == 'waiting'
        first = orb.grab().toImage()
        QTest.qWait(120)
        assert first == orb.grab().toImage()
        orb.set_microphone('off', '')
        assert orb.grab().toImage() != first  # Icon/color remain meaningful without motion.
    finally:
        orb.close()


@pytest.mark.parametrize('microphone,title', [('inactive', 'Микрофон не записывает'),
                                            ('off', 'Микрофон выключен'), ('error', 'Ошибка микрофона')])
def test_compact_speech_animates_without_changing_microphone(app, microphone, title):
    from eidos.ui.floating import FloatingMascot
    widget = FloatingMascot()
    widget.show()
    try:
        widget.set_microphone(microphone, 'Подключите устройство' if microphone == 'error' else '')
        widget.set_status('speaking', 'Ответ')
        widget.set_level(.07)
        QTest.qWait(300)
        before = widget.mascot.grab().toImage()
        widget.set_level(.015)
        QTest.qWait(130)
        assert widget.mascot.grab().toImage() != before
        assert widget.microphone_label.text() == title
        assert 'Говорю' in widget.status_label.text()
        widget.set_status('paused', 'Озвучка на паузе')
        QTest.qWait(300)
        paused = widget.mascot.grab().toImage()
        QTest.qWait(130)
        assert paused == widget.mascot.grab().toImage()
        assert widget.mascot.microphone_state == microphone
    finally:
        widget.close()


def test_recovered_microphone_does_not_leave_error_in_response(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        background = window.background
        background.status('ready', 'Можно начать команду')
        background.wake.microphone_changed.emit('error', 'Подключите микрофон')
        background._wake_status('Слово активации недоступно: Подключите микрофон')
        assert 'Подключите' in background.floating.status_label.text()
        background.wake.microphone_changed.emit('inactive', '')
        background.wake.microphone_changed.emit('waiting', '')
        assert 'Подключите' not in background.floating.status_label.text()
        assert 'Подключите' not in window.voice.operation.text()
        assert 'готов' in background.floating.status_label.text().lower()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
