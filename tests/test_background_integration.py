from dataclasses import replace
import pytest
from eidos.core.config import AppConfig, ConfigStore
from eidos.core.shortcuts import configured_shortcuts
from test_ui import app, wait_until

def test_background_defaults_and_conflicting_voice_key(tmp_path):
    config = AppConfig()
    assert not config.close_to_tray and not config.wake_word_enabled
    assert config.voice_hotkey == 'Ctrl+Alt+V'
    assert 'voice' in configured_shortcuts(config)
    with pytest.raises(ValueError):
        replace(config, voice_hotkey=config.translation_capture_hotkey).validate()
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(config, floating_enabled=True, tts_rate=20))
    assert store.load().tts_rate == 20

def test_reset_translation_controls(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from eidos.ui.main_window import MainWindow
    store = ConfigStore(tmp_path / 'config.json')
    store.save(AppConfig(translation_source_language='en', translation_target_language='de', translation_show_overlay=False))
    window = MainWindow(store)
    try:
        wait_until(app, lambda: not window.controller.discovering)
        monkeypatch.setattr(QMessageBox, 'question', lambda *_: QMessageBox.StandardButton.Yes)
        window._reset_settings()
        assert window.translation.target.currentData() == 'ru'
        assert window.translation.source.currentData() == 'auto'
        assert window.translation.show_overlay.isChecked()
    finally:
        window.request_exit() if hasattr(window, 'request_exit') else window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning() and not window.agent_controller.thread.isRunning())

def test_close_to_tray_keeps_workers_until_explicit_exit(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    store = ConfigStore(tmp_path / 'config.json')
    store.save(AppConfig(close_to_tray=True))
    window = MainWindow(store)
    try:
        monkeypatch.setattr(window.background, 'tray_available', lambda: True)
        window.show()
        window.close()
        assert not window.isVisible()
        assert window.controller.thread.isRunning()
        assert not window._closing
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)

def test_translation_adapter_delegates_and_requires_provider():
    from PyQt6.QtCore import QRectF
    from eidos.modules.ocr.engine import TextLine
    from eidos.modules.ocr.interface import JonSnowTranslator
    import threading
    class OCR:
        def recognize(self, image, source):
            return [TextLine('Hello', QRectF(0, 0, 30, 10))]
    class Translate:
        def translate(self, text, source, target, **kwargs):
            return 'Привет'
    adapter = JonSnowTranslator(ocr=OCR(), translator=Translate())
    with pytest.raises(ValueError):
        adapter.process(None, 'en', 'ru', '', threading.Event())
    assert adapter.process(None, 'en', 'ru', 'google', threading.Event())[0].translation == 'Привет'

def test_voice_cycle_runs_hidden_without_network(app, tmp_path, monkeypatch):
    from eidos.ui.main_window import MainWindow
    from eidos.modules.voice.worker import VoiceWorker
    from eidos.modules.voice.controller import VoiceController
    import numpy as np
    class Recorder:
        def record(self, device, stop, cancel, started):
            started()
            return np.ones(16000, dtype=np.float32)
    class STT:
        def transcribe(self, audio, config, cache, progress, cancel):
            progress('transcribing', 'Распознаю')
            return 'Привет'
    monkeypatch.setattr('eidos.ui.main_window.VoiceController', lambda cache, parent:
                        VoiceController(cache, parent, VoiceWorker(recorder=Recorder(), stt=STT())))
    store = ConfigStore(tmp_path / 'config.json')
    store.save(AppConfig(speak=False))
    window = MainWindow(store)
    window.controller.worker.commands.handle = lambda text: 'Привет, готов помочь.'
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.hide()
        window.background.voice_action()
        wait_until(app, lambda: 'готов помочь' in window.voice.answer.text.toPlainText())
        assert not window.isVisible()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
        assert not window.background.speech.is_running

def test_capture_hides_and_restores_floating(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    store = ConfigStore(tmp_path / 'config.json')
    store.save(AppConfig(floating_enabled=True))
    window = MainWindow(store)
    try:
        assert window.background.floating.isVisible()
        window.background.capture_started()
        assert not window.background.floating.isVisible()
        window.background.capture_finished()
        assert window.background.floating.isVisible()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)

def test_reduced_animation_stays_off_after_save(app, tmp_path):
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window.show()
        window._persist(replace(window.config, reduce_animations=True))
        assert not window.voice.mascot.animations_enabled
        assert not window.assistant.mascot.animations_enabled
        assert not window.sidebar.logo.animations_enabled
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)

def test_cancel_capture_restores_previous_translation_layer(app):
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import QWidget
    from eidos.ui.pages.translation import TranslationPage
    page = TranslationPage()
    layer = QWidget()
    layer.show()
    page.overlay = layer
    page.region = QRect(2, 3, 100, 50)
    page.captured_image = QImage(100, 50, QImage.Format.Format_RGB32)
    page.start_capture()
    assert page.overlay is layer
    assert not layer.isVisible()
    page._cancel_selection()
    assert layer.isVisible()
    assert page.region == QRect(2, 3, 100, 50)
    page.shutdown()
    page.close()

def test_capture_error_after_previous_cancellation_restores_window(app):
    from PyQt6.QtGui import QImage
    from eidos.ui.pages.translation import TranslationPage
    page = TranslationPage()
    page.show()
    page._cancelled = True
    page.provider.setCurrentIndex(page.provider.findData(''))
    page.start_capture()
    page.captured_image = QImage(50, 50, QImage.Format.Format_RGB32)
    page._clear_selectors()
    page._process_capture()
    assert page.isVisible()
    assert 'Провайдер' in page.feedback.text()
    page.shutdown()
    page.close()

def test_translation_rate_limit_is_explained_without_retry(monkeypatch):
    from urllib.error import HTTPError
    from eidos.modules.ocr.engine import OnlineTranslator
    calls = []
    def limited(*args, **kwargs):
        calls.append(True)
        raise HTTPError('https://translate.googleapis.com', 429, 'Too Many Requests', {}, None)
    monkeypatch.setattr('eidos.modules.ocr.engine.urlopen', limited)
    with pytest.raises(RuntimeError, match='ограничил'):
        OnlineTranslator().translate('Hello', 'en', 'ru')
    assert len(calls) == 1
