from dataclasses import replace
from PyQt6.QtWidgets import QLabel
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_removed_destinations_are_inaccessible_and_documents_have_grants(app, tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    try:
        assert [button.accessibleName() for button in window.sidebar.buttons] == [
            'Главная', 'Экран и перевод', 'Камера и жесты', 'Инструменты', 'Настройки']
        assert window.pages.indexOf(window.assistant) == -1
        window.navigate(6)
        previous = window.pages.currentWidget()
        for removed in (5, 7):
            window.navigate(removed)
            assert window.pages.currentWidget() is previous
        assert window.tools.isAncestorOf(window.assistant.select_files)
        assert window.tools.isAncestorOf(window.assistant.select_folder)
        assert window.tools.isAncestorOf(window.assistant.forget_files)
        assert not window.settings.profile_row.isVisibleTo(window.settings)
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
