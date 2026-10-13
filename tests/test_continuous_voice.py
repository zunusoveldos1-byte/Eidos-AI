from test_ui import app, wait_until
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow

def test_mode_toggle_greeting_resume_and_collapse(app, tmp_path, monkeypatch):
    w = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        b = w.background
        b.timer.stop()
        w.controller.discovering = False
        calls, spoken = [], []
        monkeypatch.setattr(w.controller, 'start', lambda c: calls.append(c))
        monkeypatch.setattr(b, 'speak', lambda text, **kw: spoken.append(text) or True)
        b.voice_action()
        assert b.listen_enabled and calls[-1].continuous_listening
        b._microphone_changed('manual', 'enabled', '')
        b._tick()
        assert spoken == ['Привет! Я Эйдос. Слушаю вас']
        b._quiet_until = 0
        b._tick()
        assert len(calls) >= 2
        b._microphone_changed('manual', 'enabled', '')
        b._tick()
        assert len(spoken) == 1
        w.placement.to_desktop()
        w.placement.hide_character()
        assert not b.floating.isVisible() and b.listen_enabled
        w.placement.show_character()
        assert b.floating.isVisible() and b.listen_enabled
        b.voice_action()
        assert not b.listen_enabled and b.paused and not b.speech.active
        assert w.voice.mascot.microphone_state == 'off'
    finally:
        w.request_exit()
        wait_until(app, lambda: w._allow_close)
