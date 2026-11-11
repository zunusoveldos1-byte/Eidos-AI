from dataclasses import replace
from PyQt6.QtCore import Qt, QRect, QPoint, QRectF, QEvent
from PyQt6.QtGui import QPixmap, QColor, QImage
from PyQt6 import sip
from PyQt6.QtTest import QTest
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.screen_translation import RegionSelector
from eidos.ui.pages.translation import TranslationPage
from eidos.modules.ocr.engine import TextLine
from eidos.ui.localized import QWidget
from test_ui import app, wait_until


def test_capture_hotkey_does_not_navigate_or_show_window(app, tmp_path, monkeypatch):
    store = ConfigStore(tmp_path / 'config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    try:
        window.navigate(6)
        window.hide()
        calls = []
        monkeypatch.setattr(window.translation, 'start_capture', lambda: calls.append(True))
        window._translation_hotkey('capture')
        assert calls and window.pages.currentIndex() == 6 and not window.isVisible()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_selector_glow_lifecycle_and_full_monitor_geometry(app):
    screen = app.primaryScreen()
    snapshot = QPixmap(screen.size())
    snapshot.fill(QColor('white'))
    selector = RegionSelector(screen, snapshot)
    try:
        selector.show()
        assert selector.geometry() == screen.geometry()
        assert selector.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert selector.pulse_timer.isActive()
        QTest.keyClick(selector, Qt.Key.Key_Escape)
        assert not selector.pulse_timer.isActive()
        assert not selector.isVisible()
    finally:
        selector.close()


def test_minimal_page_has_no_visible_text_cards_and_error_keeps_region(app):
    page = TranslationPage()
    page.show()
    try:
        for widget in (page.original.text, page.translated.text, page.recognize_button,
                       page.paste_button, page.copy_translation):
            assert not widget.isVisibleTo(page)
        page.region = QRect(30, 40, 200, 80)
        page.selected_screen = app.primaryScreen()
        page.hide()
        page._failed('Network unavailable')
        assert page.region == QRect(30, 40, 200, 80)
        assert page.overlay_controls.isVisible() and not page.isVisible()
        page.dismiss_overlay()
        assert not page.isVisible()
    finally:
        page.shutdown()
        page.close()


def test_result_escape_deletes_both_layers_and_keeps_windows_visible(app):
    page, target = TranslationPage(), QWidget()
    page.show()
    target.show()
    try:
        page.region = QRect(30, 40, 200, 80)
        page.selected_screen = app.primaryScreen()
        page.captured_image = QImage(200, 80, QImage.Format.Format_RGB32)
        page.captured_image.fill(QColor('white'))
        page._show_result([TextLine('Hello', QRectF(10, 10, 100, 30), 'Привет')])
        layer, controls = page.overlay, page.overlay_controls
        assert page.isVisible() and target.isVisible()
        assert not controls.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        app.processEvents()
        QTest.keyClick(controls, Qt.Key.Key_Escape)
        assert page.overlay is None and page.overlay_controls is None
        assert not layer.isVisible() and not controls.isVisible()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert sip.isdeleted(layer) and sip.isdeleted(controls)
        assert page.isVisible() and target.isVisible()
        assert not page.isMinimized() and not target.isMinimized()
    finally:
        page.shutdown()
        page.close()
        target.close()


def test_capture_cancel_preserves_previous_main_window_visibility(app):
    page = TranslationPage()
    try:
        for visible in (True, False):
            page.setVisible(visible)
            page.start_capture()
            assert not page.isVisible()
            page._cancel_selection()
            assert page.isVisible() == visible
            assert not page.isMinimized()
    finally:
        page.shutdown()
        page.close()
