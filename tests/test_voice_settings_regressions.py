from dataclasses import replace
from eidos.core.state import State, StateMachine
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.localized import QMessageBox
from test_ui import app, wait_until


def test_streaming_model_can_load_before_microphone_and_restart_after_cancel():
    machine = StateMachine()
    for state in (State.STARTING, State.LOADING, State.RECORDING, State.TRANSCRIBING,
                  State.IDLE, State.STARTING, State.LOADING, State.IDLE, State.STARTING,
                  State.RECORDING, State.TRANSCRIBING):
        machine.transition(state)
    assert machine.state == State.TRANSCRIBING


def test_reset_keeps_hidden_character_and_placement(app, tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), mascot_hidden=True, floating_enabled=True,
                       floating_x=300, floating_y=200, voice_hotkey_enabled=False,
                       translation_hotkeys_enabled=False))
    window = MainWindow(store)
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    try:
        window._reset_settings()
        assert window.config.mascot_hidden
        assert window.config.floating_enabled
        assert (window.config.floating_x, window.config.floating_y) == (300, 200)
        assert window.mascot_stage.isHidden()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
