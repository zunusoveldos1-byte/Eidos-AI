from dataclasses import replace
import json

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QWidget
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.icons import icon
from test_ui import app, wait_until


@pytest.fixture
def window(app, tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    window.show()
    QTest.qWait(300)
    yield window
    window.request_exit()
    wait_until(app, lambda: window._allow_close)


def test_sidebar_shortcut_roundtrip_and_content_expands(window, app):
    before = window.pages.width()
    QTest.keyClick(window, Qt.Key.Key_B, Qt.KeyboardModifier.ControlModifier)
    QTest.qWait(320)
    wait_until(app, lambda: window.sidebar_animation.state().name == 'Stopped')
    assert window.sidebar.isHidden()
    assert window.pages.width() > before
    assert window.store.load().sidebar_collapsed
    assert window.menu_button.isVisible()
    assert window.menu_button.toolTip() == 'Показать меню'
    window.menu_button.click()
    QTest.qWait(320)
    wait_until(app, lambda: window.sidebar_animation.state().name == 'Stopped')
    assert not window.sidebar.isHidden()
    assert not window.store.load().sidebar_collapsed


def test_no_extra_title_strip_and_menu_button_stays_accessible(window, app):
    assert window.findChild(QWidget, 'titleBar') is None
    assert window.workspace.y() == 0
    assert window.workspace.height() == window.centralWidget().height()
    assert window.pages.y() == 0
    window.assistant.feedback.setText('Проверка сообщения службы')
    app.processEvents()
    assert not window.assistant.feedback.isVisible()
    assert window.toasts.notice.isVisible()
    assert window.pages.y() == 0
    window.assistant.feedback.setText('')
    app.processEvents()
    assert window.pages.y() == 0
    assert window.menu_button.parentWidget() is window.sidebar
    assert window.menu_button.size().width() == window.menu_button.size().height() == 34
    assert window.menu_button.x() + window.menu_button.width() <= window.sidebar.width()
    assert window.menu_button.toolTip() == 'Скрыть меню'
    assert window.menu_button.icon().cacheKey() == icon('chevron-left', '#25E6A1').cacheKey()
    assert not window.windowIcon().isNull()
    window.menu_button.click()
    QTest.qWait(320)
    assert window.menu_button.parentWidget() is window.workspace
    assert window.menu_button.x() == 12
    assert window.menu_button.icon().cacheKey() == icon('chevron-right', '#25E6A1').cacheKey()
    for page in window.sidebar.page_ids:
        window.navigate(page)
        app.processEvents()
        assert window.menu_button.isVisible()
        assert window.menu_button.toolTip() == 'Показать меню'
    window.menu_button.click()
    QTest.qWait(320)
    wait_until(app, lambda: window.sidebar_animation.state().name == 'Stopped')
    assert window.menu_button.parentWidget() is window.sidebar
    assert window.menu_button.isVisible()


def test_menu_button_restores_sidebar_from_compact_mode(window, app):
    window.set_compact(True)
    app.processEvents()
    assert window.menu_button.isVisible()
    assert window.menu_button.toolTip() == 'Показать меню'
    window.menu_button.click()
    QTest.qWait(320)
    assert not window.compact and not window.sidebar.isHidden()
    assert window.menu_button.toolTip() == 'Скрыть меню'


def test_home_motion_stops_when_hidden_minimized_or_disabled(window, app):
    assert window.home.motion_timer.isActive()
    window.navigate(6)
    assert not window.home.motion_timer.isActive()
    window.navigate(0)
    window.showMinimized()
    app.processEvents()
    assert not window.home.motion_timer.isActive()
    window.showNormal()
    QTest.qWait(50)
    assert window.home.motion_timer.isActive()
    window.config = replace(window.config, reduce_animations=True)
    window._apply_preferences()
    assert not window.home.motion_timer.isActive()


def test_home_request_uses_existing_chat_and_app_tool(window, monkeypatch):
    requests = []
    monkeypatch.setattr(window, '_start_agent_task', lambda kind, payload=None: requests.append((kind, payload)) or True)
    window.home.app_button.click()
    window.app_menu.actions()[0].trigger()
    assert requests[-1] == ('tool', ('open_notepad', {}))
    window.app_menu.hide()


def test_camera_indicator_reports_service_status(window):
    window.gestures.status_changed.emit('Камера включена')
    assert window.home.camera_status.text() == 'Камера: вкл.'
    window.gestures.status_changed.emit('Камера выключена')
    assert window.home.camera_status.text() == 'Камера: выкл.'
    window.gestures.status_changed.emit('Ошибка камеры: устройство занято')
    assert window.home.camera_status.text() == 'Камера: ошибка'


def test_small_home_reflows_without_horizontal_overflow(window, app):
    window.resize(780, 560)
    QTest.qWait(350)
    assert window.home.scroll.horizontalScrollBar().maximum() == 0
    assert window.home.content.width() <= window.home.scroll.viewport().width()
    assert window.home.isAncestorOf(window.voice.action_button)
    assert not window.windowIcon().isNull()
    assert window.home.translate_button.height() >= 100
    assert window.home.app_button.height() >= 100


def test_system_reduced_motion_and_reset_sidebar(window, monkeypatch):
    monkeypatch.setattr('eidos.ui.main_window.system_reduced_motion', lambda: True)
    window._apply_preferences()
    assert not window.home.motion_timer.isActive()
    window.menu_button.click()
    assert window.sidebar.isHidden()
    assert window.sidebar_animation.state().name == 'Stopped'
    window.config = replace(window.config, sidebar_collapsed=False)
    window._apply_preferences()
    assert not window.sidebar.isHidden()


def test_capture_and_voice_cards_use_existing_actions(window, monkeypatch):
    calls = []
    window.voice.action_requested.disconnect()
    window.voice.action_requested.connect(lambda: calls.append('voice'))
    monkeypatch.setattr(window.translation, 'start_capture', lambda: calls.append('capture'))
    window.home.mic_button.setEnabled(True)
    window.home.mic_button.click()
    assert calls == ['voice'] and window.pages.currentIndex() == 0
    window.navigate(0)
    window.home.translate_button.click()
    assert calls == ['voice', 'capture'] and window.pages.currentIndex() == 0


def test_home_has_no_chat_controls_and_keeps_two_equal_actions(window, app):
    from PyQt6.QtWidgets import QLineEdit
    assert not window.home.findChildren(QLineEdit)
    assert not hasattr(window.home, 'send_button')
    assert not hasattr(window.home, 'voice_button')
    assert window.sidebar.group.button(1) is None
    assert len(window.sidebar.buttons) == 5
    assert window.home.translate_button.width() == window.home.app_button.width()
    assert window.home.mic_button is window.voice.action_button
    window.controller.microphone_changed.emit('error', 'Permission denied')
    assert 'Готов помочь' not in window.home.status.text()
    assert window.voice.title.text() == 'Нет доступа к микрофону'


@pytest.mark.parametrize('occupied_default', [False, True])
def test_old_global_menu_shortcut_migrates_without_resetting_other_preferences(tmp_path, occupied_default):
    store = ConfigStore(tmp_path / 'config.json')
    values = {'voice_hotkey': 'Ctrl+B', 'translation_capture_hotkey': 'Ctrl+8',
              'speak': False, 'reduce_animations': True}
    if occupied_default:
        values['translation_repeat_hotkey'] = AppConfig().voice_hotkey
    store.path.write_text(json.dumps(values), encoding='utf-8')
    loaded = store.load()
    assert not loaded.speak and loaded.reduce_animations
    assert loaded.voice_hotkey != 'Ctrl+B'
    if not occupied_default:
        assert loaded.voice_hotkey == AppConfig().voice_hotkey
    else:
        assert loaded.translation_repeat_hotkey == AppConfig().voice_hotkey
    assert loaded.translation_capture_hotkey == AppConfig().translation_capture_hotkey
    assert store.warning and 'Ctrl+B' in store.warning
