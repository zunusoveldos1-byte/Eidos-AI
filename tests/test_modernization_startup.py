from pathlib import Path
from eidos.core.config import AppConfig, ConfigStore


def test_startup_command_is_absolute_and_windows_quoted(tmp_path):
    from eidos.core.startup import startup_command
    command = startup_command(tmp_path / 'Python App' / 'python.exe', tmp_path / 'Eidos App' / 'launcher.py')
    assert command.startswith('"')
    assert '" "' in command
    assert 'launcher.py"' in command
    assert '-c' not in command


def test_single_instance_lock_released_after_clean_exit(app, tmp_path):
    from eidos.core.instance import SingleInstance
    first = SingleInstance(tmp_path)
    second = SingleInstance(tmp_path)
    assert first.acquire()
    assert not second.acquire()
    first.close()
    assert second.acquire()
    second.close()


def test_new_settings_roundtrip_and_validate(tmp_path):
    from dataclasses import replace
    import pytest
    config = replace(AppConfig(), startup_enabled=True, ui_language='ky', theme='light', accent_color='#458BEA')
    store = ConfigStore(tmp_path / 'config.json')
    store.save(config)
    assert store.load() == config
    with pytest.raises(ValueError):
        replace(config, accent_color='url(https://example.org)').validate()

from test_ui import app
