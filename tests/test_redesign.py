from dataclasses import replace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QStackedWidget

from eidos.core.config import AppConfig, ConfigStore
from eidos.modules.voice.recorder import Microphone
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def close_window(window, app):
    window.close()
    wait_until(app, lambda: not window.controller.thread.isRunning() and not window.agent_controller.thread.isRunning())
    app.processEvents()


def test_appearance_settings_validate_and_roundtrip(tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    config = replace(AppConfig(), always_on_top=True, mascot_animation=False)
    store.save(config)
    assert store.load() == config
    with pytest.raises(ValueError):
        replace(config, mascot_animation='yes').validate()


def test_navigation_and_future_actions_disabled(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        assert isinstance(window.pages, QStackedWidget)
        assert window.pages.count() == 6
        for index, button in enumerate(window.sidebar.buttons):
            button.click()
            assert window.pages.currentIndex() == index
            assert button.isChecked()
        assert not window.gestures.camera_button.isEnabled()
        assert not window.translation.select_button.isEnabled()
        window.home.voice_button.click()
        assert window.pages.currentIndex() == 1
        window.sidebar.assistant_button.click()
        assert window.pages.currentIndex() == 5
    finally:
        close_window(window, app)


def test_settings_draft_save_reset_and_voice_sync(app, tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / 'config.json')
    window = MainWindow(store)
    try:
        wait_until(app, lambda: not window.controller.discovering)
        settings = window.settings
        settings.speak.setChecked(False)
        settings.animation.setChecked(False)
        settings.model.setCurrentText('tiny')
        settings.on_top.setChecked(True)
        settings.tts_voice.setCurrentIndex(settings.tts_voice.findData('ru-RU-DmitryNeural'))
        assert window.config.speak is True
        settings.save_button.click()
        assert not store.load().speak
        assert not window.voice.speak.isChecked()
        assert not window.voice.mascot.animations_enabled
        assert store.load().whisper_model == 'tiny'
        assert store.load().tts_voice == 'ru-RU-DmitryNeural'
        assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        monkeypatch.setattr(QMessageBox, 'question', lambda *_, **__: QMessageBox.StandardButton.No)
        settings.reset_button.click()
        assert store.load().whisper_model == 'tiny'
        monkeypatch.setattr(QMessageBox, 'question', lambda *_, **__: QMessageBox.StandardButton.Yes)
        settings.reset_button.click()
        assert store.load() == AppConfig()
        assert not window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        window.voice.speak.setChecked(False)
        assert not store.load().speak
        assert not settings.speak.isChecked()
    finally:
        close_window(window, app)


def test_voice_real_signal_binding_and_copy(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.controller.transcript.emit('Проверка настоящего сигнала')
        window.controller.reply.emit('Ответ из контроллера')
        assert window.voice.recognized.text.toPlainText() == 'Проверка настоящего сигнала'
        window.voice.recognized.copy_button.click()
        assert app.clipboard().text() == 'Проверка настоящего сигнала'
        window._state_changed('recording', 'Запись…')
        assert window.voice.mascot.state == 'listening'
        assert window.voice.action_button.text() == 'Остановить'
        window._state_changed('loading', 'Первая загрузка модели: требуется интернет')
        assert window.voice.mascot.state == 'thinking'
        assert 'интернет' in window.voice.operation.text()
        window._state_changed('error', 'Ошибка микрофона')
        assert window.voice.mascot.state == 'error'
        window._state_changed('idle', 'Готово')
        assert window.voice.mascot.state == 'ready'
    finally:
        close_window(window, app)


def test_compact_mode_and_small_page_scroll(app, tmp_path):
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window.show()
        window.set_compact(True)
        app.processEvents()
        assert window.pages.currentIndex() == 1
        assert window.sidebar.isHidden()
        assert not window.return_button.isHidden()
        window.set_compact(False)
        assert not window.sidebar.isHidden()
        window.resize(820, 580)
        window.navigate(4)
        app.processEvents()
        assert window.settings.scroll.widgetResizable()
        assert window.settings.scroll.verticalScrollBar().maximum() > 0
    finally:
        close_window(window, app)


def test_window_buttons_run_existing_voice_controller(app, tmp_path, monkeypatch):
    import numpy as np
    from eidos.modules.voice.controller import VoiceController
    from eidos.modules.voice.worker import VoiceWorker

    class Recorder:
        def record(self, device, stop, cancel, started):
            started()
            while not stop.wait(0.01) and not cancel.is_set():
                pass
            return np.ones(16000, dtype=np.float32)

    class STT:
        def transcribe(self, audio, config, cache, progress, cancel):
            progress('transcribing', 'Распознавание')
            return 'Привет'

    def controller(cache, parent):
        return VoiceController(cache, parent, VoiceWorker(recorder=Recorder(), stt=STT()))

    monkeypatch.setattr('eidos.ui.main_window.VoiceController', controller)
    store = ConfigStore(tmp_path / 'config.json')
    store.save(AppConfig(speak=False))
    window = MainWindow(store)
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window._devices([Microphone(1, 'Unit test mic')])
        window.navigate(1)
        assert window.voice.recognized.text.toPlainText() == ''
        window.voice.action_button.click()
        wait_until(app, lambda: window.current_state == 'recording')
        assert window.voice.action_button.text() == 'Остановить'
        window.voice.action_button.click()
        wait_until(app, lambda: window.current_state == 'idle')
        assert window.voice.recognized.text.toPlainText() == 'Привет'
        assert 'Привет' in window.voice.answer.text.toPlainText()
    finally:
        close_window(window, app)
