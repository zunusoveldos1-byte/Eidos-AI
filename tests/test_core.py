from datetime import datetime
import json

import pytest

from eidos.core.commands import CommandHandler
from eidos.core.config import AppConfig, ConfigStore
from eidos.core.state import State, StateMachine


@pytest.mark.parametrize('text', ['Привет', '  ПРИВЕТ!!! ', 'привет.'])
def test_greeting_normalization(text):
    assert 'Привет' in CommandHandler().handle(text)


def test_time_and_date_use_injected_local_clock():
    handler = CommandHandler(now=lambda: datetime(2026, 10, 9, 17, 4))
    assert handler.handle('Который час?') == 'Сейчас 17:04.'
    assert handler.handle('Какая сегодня дата?') == 'Сегодня 9 октября 2026 года.'


def test_help_and_unknown_and_empty():
    handler = CommandHandler()
    assert 'Который час' in handler.handle('Помощь')
    assert 'не подключена' in handler.handle('Напиши роман')
    assert 'не распознана' in handler.handle('   ')
    assert 'не подключена' in handler.handle('это не привет')


def test_config_roundtrip(tmp_path):
    store = ConfigStore(tmp_path / 'settings.json')
    config = AppConfig(microphone=3, microphone_name='USB', speak=False, whisper_model='tiny')
    store.save(config)
    assert store.load() == config
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('payload', ['{', '[]', '{"speak": "false"}', '{"microphone": -1}', '{"whisper_model": "unknown"}'])
def test_invalid_config_falls_back_with_warning(tmp_path, payload):
    path = tmp_path / 'settings.json'
    path.write_text(payload, encoding='utf-8')
    store = ConfigStore(path)
    assert store.load() == AppConfig()
    assert store.warning


def test_missing_config_and_unknown_keys(tmp_path):
    store = ConfigStore(tmp_path / 'settings.json')
    assert store.load() == AppConfig()
    assert store.warning is None
    store.path.write_text(json.dumps({'future': 1, 'speak': False}), encoding='utf-8')
    assert store.load().speak is False


def test_invalid_config_is_not_written(tmp_path):
    store = ConfigStore(tmp_path / 'settings.json')
    with pytest.raises(ValueError):
        store.save(AppConfig(device='other'))
    assert not store.path.exists()


def test_state_cycle_and_repeated_press():
    machine = StateMachine()
    for state in [State.STARTING, State.RECORDING, State.LOADING, State.TRANSCRIBING, State.SYNTHESIZING, State.PLAYING, State.IDLE]:
        machine.transition(state)
        assert machine.state == state
    machine.transition(State.STARTING)
    with pytest.raises(ValueError):
        machine.transition(State.STARTING)


def test_error_recovery_and_shutdown_are_terminal():
    machine = StateMachine()
    machine.transition(State.STARTING)
    machine.transition(State.ERROR)
    machine.transition(State.IDLE)
    machine.transition(State.CLOSING)
    with pytest.raises(ValueError):
        machine.transition(State.IDLE)


def test_cannot_transcribe_without_recording():
    with pytest.raises(ValueError):
        StateMachine().transition(State.TRANSCRIBING)
