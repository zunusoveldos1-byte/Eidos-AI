from dataclasses import replace
import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt
from eidos.core.config import AppConfig
from test_ui import app, wait_until
from test_home_refresh import window


def test_voice_minimal_controls_and_settings_are_reparented(window, app):
    window.config = replace(window.config, speak=False)
    window.navigate(1)
    app.processEvents()
    assert not window.mascot_stage.isVisible()
    assert not window.voice.input_level.isVisible()
    assert not window.voice.response_status.isVisible()
    assert window.settings.isAncestorOf(window.voice.microphone)
    assert window.settings.isAncestorOf(window.settings.wake_card)
    assert not window.voice.recognized.isVisible()
    assert not window.voice.answer.isVisible()
    window.controller.transcript.emit('Реальная команда')
    window.controller.reply.emit('Реальный ответ')
    assert 'Реальная команда' in window.assistant.history.toPlainText()
    assert 'Реальный ответ' in window.assistant.history.toPlainText()


def test_voice_waves_freeze_in_silence_and_ignore_reply(window, app):
    window.navigate(1)
    orb = window.voice.mascot
    window.controller.microphone_changed.emit('enabled', '')
    assert window.voice.title.text() == 'Слушаю вас'
    assert not orb.visual_timer.isActive()
    window.controller.speech_activity.emit(.07, True)
    QTest.qWait(140)
    assert orb.phase > 0 and orb.visual_timer.isActive()
    window.controller.speech_activity.emit(.002, False)
    QTest.qWait(450)
    assert not orb.visual_timer.isActive()
    phase = orb.phase
    QTest.qWait(100)
    assert orb.phase == phase
    window.background.status('playing', 'Ответ')
    window.background.speech_level(.5)
    window.controller.speech_activity.emit(.2, True)
    QTest.qWait(100)
    assert not orb.visual_timer.isActive()


def test_sleep_is_separate_from_off_and_wake_hint_is_honest(window, monkeypatch):
    monkeypatch.setattr(window.background, '_try_voice', lambda: None)
    window.navigate(1)
    window.background.toggle_pause()
    assert window.voice.title.text() == 'Спит'
    assert window.voice.operation.text() == 'Нажмите, чтобы разбудить'
    window.background.voice_action()
    assert not window.background.sleeping
    window.background.voice_action()
    assert window.voice.title.text() == 'Микрофон выключен'
    assert window.voice.operation.text() == 'Нажмите, чтобы включить'
    window.background.paused = False
    window.background.wake.microphone_changed.emit('waiting', '')
    assert window.voice.title.text() == 'Спит'
    assert window.voice.operation.text() == 'Нажмите, чтобы разбудить'
    window.config = replace(window.config, wake_word_enabled=True)
    monkeypatch.setattr(type(window.background.wake), 'is_running', property(lambda self: True))
    window.background._refresh_microphone()
    assert window.voice.operation.text() == 'Разбудите голосом'
    monkeypatch.undo()


@pytest.mark.parametrize('message,title', [('Device not found', 'Микрофон не найден'),
                                         ('Permission denied', 'Нет доступа к микрофону')])
def test_specific_error_and_recovery(window, message, title):
    window.controller.microphone_changed.emit('error', message)
    assert window.voice.title.text() == title
    assert window.voice.operation.text()
    window.controller.microphone_changed.emit('enabled', '')
    assert window.voice.title.text() == 'Слушаю вас'


def test_voice_keyboard_and_centering_without_menu(window, app):
    window.navigate(1)
    window.resize(780, 560)
    app.processEvents()
    orb = window.voice.mascot
    assert orb.parentWidget().rect().contains(orb.geometry())
    assert abs(orb.geometry().center().x() - orb.parentWidget().rect().center().x()) <= 1
    calls = []
    orb.clicked.disconnect()
    orb.clicked.connect(lambda: calls.append(True))
    orb.setEnabled(True)
    orb.setFocus()
    QTest.keyClick(orb, Qt.Key.Key_Return)
    assert calls == [True]


def test_service_error_survives_worker_completion_and_clears_on_retry(window):
    window._state_changed('error', 'Network connection failed')
    assert window.voice.title.text() == 'Нет подключения'
    window._state_changed('idle', 'Ошибка. Можно повторить запись; подробности в журнале.')
    assert window.voice.title.text() == 'Нет подключения'
    window._state_changed('starting', 'Подготовка микрофона')
    assert window.voice.mascot.ui_state != 'error'


def test_capture_vad_uses_same_stream_and_marks_silence(monkeypatch):
    import sys
    from threading import Event
    from types import SimpleNamespace
    import numpy as np
    from eidos.modules.voice.recorder import Recorder
    stop, cancel = Event(), Event()
    captures, activity = [], []
    class Stream:
        active = True
        def __init__(self, **kwargs):
            captures.append(kwargs['device'])
            self.callback = kwargs['callback']
        def start(self):
            for value in (.002, .06, .002):
                self.callback(np.full(512, int(value * 32768), dtype='<i2').tobytes(), 512, None, False)
            stop.set()
        def abort(self): pass
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream,
        query_devices=lambda *_: {'default_samplerate': 16000}, check_input_settings=lambda **_: None))
    recorder = Recorder()
    recorder.vad = SimpleNamespace(reset=lambda: None, __call__=None)
    class VAD:
        def reset(self): pass
        def __call__(self, pcm): return float(np.max(np.frombuffer(pcm, dtype='<i2')) > 1000)
    recorder.vad = VAD()
    recorder.configure(replace(AppConfig(), speak=False))
    recorder.activity_callback = lambda level, voiced: activity.append(voiced)
    recorder.record(7, stop, cancel, lambda: None)
    assert captures == [7]
    assert activity == [False, True, False]


def test_leaving_voice_keeps_manually_latched_microphone(window, monkeypatch):
    window.navigate(1)
    calls = []
    window.background.listen_enabled = True
    window.current_state = 'recording'
    monkeypatch.setattr(window.controller, 'cancel', lambda: calls.append('cancel'))
    window.navigate(6)
    assert calls == []
    assert not window.background.paused and window.background.listen_enabled
