from dataclasses import replace
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_settings_destinations_and_dynamic_provider_fields(app, tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    try:
        s, ui = window.settings, window.assistant
        assert [s.tabs.tabText(i) for i in range(s.tabs.count())] == [
            'Общие', 'Модель', 'Подключения', 'Голос', 'Экран и перевод']
        assert not s.general_page.isAncestorOf(s.stt_engine)
        assert window.voice.config_tabs.widget(0).isAncestorOf(s.vosk_model_path)
        assert window.voice.config_tabs.widget(0).isAncestorOf(s.voice_hotkey)
        assert s.tabs.widget(4).isAncestorOf(s.capture_hotkey)
        window.navigate(4)
        window.show()
        s.tabs.setCurrentIndex(1)
        ui.provider.setCurrentIndex(ui.provider.findData('ollama'))
        assert not ui.cloud_model.isVisibleTo(s)
        assert ui.model_name.isVisibleTo(s)
        ui.provider.setCurrentIndex(ui.provider.findData('openai'))
        assert ui.cloud_model.isVisibleTo(s)
        assert not ui.model_name.isVisibleTo(s)
        s.tabs.setCurrentIndex(3)
        s.stt_engine.setCurrentIndex(s.stt_engine.findData('vosk'))
        assert s.vosk_model_path.isVisibleTo(s)
        assert not s.model.isVisibleTo(s)
        s.tts_provider.setCurrentIndex(s.tts_provider.findData('sapi'))
        assert s.sapi_voice.isVisibleTo(s)
        assert not s.tts_voice.isVisibleTo(s)
        assert s.footer.isVisibleTo(s)
        s.tabs.setCurrentIndex(4)
        s.capture_hotkey.setKeySequence('Ctrl+Shift+T')
        window._save_settings()
        saved = store.load()
        assert saved.stt_engine == 'vosk' and saved.tts_provider == 'sapi'
        assert saved.translation_capture_hotkey == 'Ctrl+Shift+T'
        assert not window.mascot_stage.isVisibleTo(window)
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
