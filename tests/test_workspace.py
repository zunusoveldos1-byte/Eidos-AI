from dataclasses import replace
import pytest
from PyQt6.QtCore import Qt
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.mascot import Mascot
from test_ui import app, wait_until


@pytest.fixture
def window(app, tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    window.show()
    wait_until(app, lambda: not window.controller.discovering)
    yield window
    window.request_exit()
    wait_until(app, lambda: window._allow_close)


def test_five_destinations_and_one_character(window):
    assert [b.accessibleName() for b in window.sidebar.buttons] == [
        'Главная', 'Экран и перевод', 'Камера и жесты', 'Инструменты', 'Настройки']
    assert window.pages.count() == 7
    assert len(window.findChildren(Mascot)) == 1
    for page in window.sidebar.page_ids:
        window.navigate(page)
        assert window.pages.currentIndex() == page
    from PyQt6.QtGui import QShortcut
    for shortcut in window.findChildren(QShortcut):
        if shortcut.key().toString() == 'Ctrl+2':
            shortcut.activated.emit()
    assert window.pages.currentIndex() == 3


def test_transfer_keeps_character_controllers_and_live_state(window):
    character = window.character
    controller, worker, playback = window.controller, window.controller.worker, window.controller.playback
    window.background.status('playing', 'Говорю')
    character._tick = 7
    window.placement.to_desktop()
    assert window.placement.desktop.isVisible()
    assert character.parentWidget() is window.placement.desktop
    assert character.state == 'speaking'
    assert window.controller is controller and window.controller.worker is worker
    assert window.controller.playback is playback
    assert window.placement.desktop.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.placement.to_app()
    assert character.parentWidget() is window.mascot_stage
    assert not window.placement.desktop.isVisible()
    assert character.state == 'speaking'


def test_start_maximized_and_tray_setting_are_independent(window, monkeypatch):
    window.show_startup()
    assert window.isMaximized()
    monkeypatch.setattr(window.background, 'tray_available', lambda: True)
    window.config = replace(window.config, start_in_tray=True, close_to_tray=False)
    window.show_startup()
    assert not window.isVisible()
    monkeypatch.setattr(window.background, 'tray_available', lambda: False)
    window.show_startup()
    assert window.isVisible() and window.isMaximized()


def test_capture_restores_single_desktop_character(window):
    window.placement.to_desktop()
    window.background.capture_started()
    assert not window.placement.desktop.isVisible()
    window.background.capture_finished()
    assert window.placement.desktop.isVisible()
    window.placement.to_app()


def test_form_ownership_without_duplicate_settings(window):
    assert window.settings.tts_voice is window.voice.tts_voice
    assert window.assistant.tabs.count() == 0
    assert window.assistant.memory_list.isAncestorOf(window.assistant.memory_list.viewport())
    assert not window.assistant.sections['Память'].isVisibleTo(window)
    assert window.settings.isAncestorOf(window.assistant.provider)
    assert window.tools.isAncestorOf(window.assistant.calendar_list)


def test_transfer_during_real_worker_recording_keeps_one_stream(window, app):
    from test_ui import WaitingRecorder
    recorder = WaitingRecorder()
    window.controller.worker.recorder = recorder
    window.controller.start(replace(window.config, speak=False))
    wait_until(app, lambda: recorder.calls == 1)
    worker = window.controller.worker
    window.placement.to_desktop()
    window.placement.to_app()
    assert window.controller.active
    assert window.controller.worker is worker
    assert recorder.calls == 1
    window.controller.cancel()
    wait_until(app, lambda: not window.controller.active)


def test_drag_does_not_click_and_keyboard_can_move_and_activate(window, app):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest
    character = window.character
    clicks = []
    character.clicked.disconnect()
    character.clicked.connect(lambda: clicks.append(True))
    original = character.x()
    QTest.mousePress(character, Qt.MouseButton.LeftButton, pos=QPoint(65, 65))
    QTest.mouseRelease(character, Qt.MouseButton.LeftButton, pos=QPoint(110, 65))
    assert clicks == [] and character.x() > original
    QTest.mouseClick(character, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    assert clicks == [True]
    QTest.keyClick(character, Qt.Key.Key_Right)
    assert window.config.mascot_app_x == character.x()
    QTest.keyClick(character, Qt.Key.Key_Space)
    assert clicks == [True, True]


def test_camera_page_stops_shared_capture_service(window, monkeypatch):
    from types import SimpleNamespace
    page = window.gestures
    started, stopped = [], []
    device = SimpleNamespace(index=3, name='Test camera', path='test')
    page._devices_ready([device])
    def start(*args):
        started.append(args)
        page.service.status_changed.emit('● Камера включена · локальная обработка')
    def stop():
        stopped.append(True)
        page.service.status_changed.emit('Камера выключена')
        page.service.stopped.emit()
    monkeypatch.setattr(page.service, 'start', start)
    monkeypatch.setattr(page.service, 'stop', stop)
    page.toggle_camera()
    assert started[0][0] == 3
    assert 'включена' in page.camera_status.text()
    assert window.home.camera_status.isVisible()
    assert window.home.camera_status.text() == 'Камера: вкл.'
    page.shutdown()
    assert stopped and window.home.camera_status.text() == 'Камера: выкл.'
    assert not page.control.isChecked()


def test_window_keeps_ownership_until_late_synthesis_finishes(window, app, monkeypatch):
    from threading import Event
    from eidos.modules.voice import speech
    entered, release = Event(), Event()
    class Provider:
        def synthesize(self, *args, **kwargs):
            entered.set()
            release.wait(3)
            return None
    monkeypatch.setattr(speech, 'EdgeTTS', Provider)
    assert window.background.speak('Проверка завершения.')
    wait_until(app, entered.is_set)
    try:
        window.request_exit()
        assert window in MainWindow._closing_windows
        assert not window._allow_close
    finally:
        release.set()
        wait_until(app, lambda: window._allow_close)
        app.processEvents()
    assert window not in MainWindow._closing_windows
