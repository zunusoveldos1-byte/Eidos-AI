from dataclasses import replace
import json

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QImage

from eidos.core.config import AppConfig, ConfigStore
from eidos.core.shortcuts import parse_shortcut
from eidos.ui.hotkeys import TranslationHotkeys
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


class Registry:
    native = False
    def __init__(self):
        self.active, self.blocked = {}, set()
    def register(self, identifier, shortcut):
        if shortcut.text in self.blocked:
            return False
        self.active[identifier] = shortcut.text
        return True
    def unregister(self, identifier):
        self.active.pop(identifier, None)


def test_hotkeys_config_roundtrip_and_old_config_migration(tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    config = replace(AppConfig(), translation_capture_hotkey='Ctrl+Shift+F8', translation_repeat_hotkey='')
    store.save(config)
    assert store.load() == config
    store.path.write_text(json.dumps({'speak': False}), encoding='utf-8')
    assert store.load().translation_capture_hotkey == 'Ctrl+Alt+T'
    assert not store.load().speak


@pytest.mark.parametrize('key', ['T', 'Shift+T', 'F12', 'Ctrl+F12', 'Ctrl+1', 'Ctrl+6', 'Ctrl+T, Ctrl+R', 'garbage'])
def test_invalid_shortcuts_are_rejected(key):
    with pytest.raises(ValueError):
        parse_shortcut(key)


def test_duplicate_shortcuts_are_rejected():
    with pytest.raises(ValueError, match='разные'):
        replace(AppConfig(), translation_repeat_hotkey='Alt+Ctrl+T').validate()


def test_shortcut_mapping_for_modifiers_and_function_keys():
    assert parse_shortcut('Ctrl+Alt+T').modifiers == 3
    assert parse_shortcut('Ctrl+Alt+T').key == ord('T')
    assert parse_shortcut('Ctrl+Shift+F8').key == 0x77
    assert parse_shortcut('Ctrl+Shift+F8').modifiers == 6
    assert parse_shortcut('') is None
    assert parse_shortcut('Ctrl+Num+8').key == 0x68


def test_conflicting_rebind_keeps_old_registrations(app):
    from PyQt6.QtWidgets import QWidget
    owner, registry = QWidget(), Registry()
    manager = TranslationHotkeys(owner, backend=registry)
    try:
        assert manager.configure(AppConfig())
        old = dict(registry.active)
        registry.blocked.add('Ctrl+Alt+H')
        changed = replace(AppConfig(), translation_capture_hotkey='Ctrl+Alt+G', translation_repeat_hotkey='Ctrl+Alt+H')
        assert not manager.configure(changed)
        assert registry.active == old
        assert manager.config == AppConfig()
        assert 'занята' in manager.message
    finally:
        manager.shutdown()
        owner.close()
    assert not registry.active


def test_editing_suspends_hotkeys_and_empty_field_disables_action(app):
    from PyQt6.QtWidgets import QWidget, QKeySequenceEdit
    owner, registry = QWidget(), Registry()
    manager = TranslationHotkeys(owner, backend=registry)
    try:
        config = replace(AppConfig(), translation_repeat_hotkey='')
        assert manager.configure(config)
        assert set(manager.actions.values()) == {'capture', 'dismiss', 'voice'}
        editor = QKeySequenceEdit(owner)
        manager._focus_changed(None, editor)
        assert not registry.active
        manager._application_state(Qt.ApplicationState.ApplicationInactive)
        assert len(registry.active) == 3
        assert manager.configure(replace(config, translation_hotkeys_enabled=False))
        assert set(manager.actions.values()) == {'voice'}
        assert manager.configure(replace(config, translation_hotkeys_enabled=False, voice_hotkey_enabled=False))
        assert not registry.active
    finally:
        manager.shutdown()
        owner.close()


def test_settings_save_applies_hotkeys_and_dispatches_actions(app, tmp_path, monkeypatch):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.settings.capture_hotkey.setKeySequence(QKeySequence('Ctrl+Shift+F8'))
        window.settings.repeat_hotkey.clear()
        window.settings.save_button.click()
        assert window.store.load().translation_capture_hotkey == 'Ctrl+Shift+F8'
        assert window.store.load().translation_repeat_hotkey == ''
        assert 'Ctrl+Shift+F8' in window.translation.hotkey_hint.text()
        calls = []
        monkeypatch.setattr(window.translation, 'start_capture', lambda: calls.append('capture'))
        window.hotkeys.activated.emit('capture')
        assert window.pages.currentIndex() == 3
        assert calls == ['capture']
        window.translation.captured_image = QImage(10, 10, QImage.Format.Format_RGB32)
        monkeypatch.setattr(window.translation, 'retry_translation', lambda: calls.append('repeat'))
        window.hotkeys.activated.emit('repeat')
        assert calls[-1] == 'repeat'
        monkeypatch.setattr(window.translation, 'dismiss_overlay', lambda *args, **kwargs: calls.append('dismiss'))
        window.hotkeys.activated.emit('dismiss')
        assert calls[-1] == 'dismiss'
    finally:
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning())
        app.processEvents()


def test_duplicate_settings_do_not_overwrite_saved_config(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.settings.repeat_hotkey.setKeySequence(QKeySequence('Ctrl+Alt+T'))
        window.settings.save_button.click()
        assert window.config == AppConfig()
        assert 'разные' in window.settings.feedback.text()
    finally:
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning())
        app.processEvents()
