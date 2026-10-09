import threading

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtTest import QTest

from eidos.modules.ocr.engine import TextLine, WindowsOCR
from eidos.ui.pages.translation import TranslationPage
from eidos.ui.screen_translation import RegionSelector, TranslationOverlay, TranslationWorker
from test_ui import app, wait_until


def test_worker_translates_lines_in_background_and_caches_duplicates(app):
    calls, results = [], []
    class OCR:
        def recognize(self, image, source):
            assert threading.current_thread() != threading.main_thread()
            return [TextLine('Hello', QRectF(5, 5, 80, 20)), TextLine('Hello', QRectF(5, 40, 80, 20))]
    class Translator:
        def translate(self, text, source, target):
            calls.append((text, source, target))
            return 'Привет'
    worker = TranslationWorker(QImage(100, 70, QImage.Format.Format_RGB32), 'en', 'ru',
                               ocr=OCR(), translator=Translator())
    worker.result.connect(results.append)
    worker.start()
    wait_until(app, lambda: not worker.isRunning())
    app.processEvents()
    assert calls == [('Hello', 'en', 'ru')]
    assert [line.translation for line in results[0]] == ['Привет', 'Привет']
    assert results[0][1].rect.y() == 40


def test_cancel_worker_suppresses_late_result(app):
    entered, release = threading.Event(), threading.Event()
    results = []
    class OCR:
        def recognize(self, image, source):
            entered.set()
            release.wait(2)
            return [TextLine('Hello', QRectF(0, 0, 70, 20))]
    worker = TranslationWorker(QImage(), 'en', 'ru', ocr=OCR())
    worker.result.connect(results.append)
    worker.start()
    wait_until(app, entered.is_set)
    worker.cancel.set()
    release.set()
    wait_until(app, lambda: not worker.isRunning())
    app.processEvents()
    assert not results


def test_no_text_and_network_failure_are_reported(app):
    class OCR:
        def recognize(self, image, source):
            return []
    errors = []
    worker = TranslationWorker(QImage(), 'en', 'ru', ocr=OCR())
    worker.failed.connect(errors.append)
    worker.start()
    wait_until(app, lambda: not worker.isRunning())
    app.processEvents()
    assert 'Текст не найден' in errors[0]
    class TextOCR:
        def recognize(self, *_):
            return [TextLine('Hello', QRectF(0, 0, 70, 20))]
    class Offline:
        def translate(self, *_):
            raise OSError('Network unavailable')
    recognized, errors = [], []
    worker = TranslationWorker(QImage(), 'en', 'ru', ocr=TextOCR(), translator=Offline())
    worker.recognized.connect(recognized.append)
    worker.failed.connect(errors.append)
    worker.start()
    wait_until(app, lambda: not worker.isRunning())
    app.processEvents()
    assert recognized == ['Hello']
    assert 'Network unavailable' in errors[0]


def test_close_window_waits_for_translation(app, tmp_path):
    from eidos.core.config import ConfigStore
    from eidos.ui.main_window import MainWindow
    entered, release = threading.Event(), threading.Event()
    class OCR:
        def recognize(self, *_):
            entered.set()
            release.wait(2)
            return []
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    page = window.translation
    page.worker = TranslationWorker(QImage(), 'en', 'ru', page, ocr=OCR())
    page.worker.finished.connect(page._finished)
    page.worker.start()
    wait_until(app, entered.is_set)
    try:
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning())
        assert not window._allow_close
        assert page.worker.cancel.is_set()
    finally:
        release.set()
        wait_until(app, lambda: window._allow_close)
        app.processEvents()


def test_selection_reverse_drag_and_escape(app):
    screen = app.primaryScreen()
    snapshot = QPixmap(screen.size())
    snapshot.fill(QColor('white'))
    selector = RegionSelector(screen, snapshot)
    selected, cancelled = [], []
    selector.selected.connect(lambda widget, rect: selected.append(rect))
    selector.cancelled.connect(lambda: cancelled.append(True))
    selector.show()
    QTest.mousePress(selector, Qt.MouseButton.LeftButton, pos=QPoint(150, 100))
    QTest.mouseMove(selector, QPoint(20, 20))
    QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    assert selected[0].topLeft() == QPoint(20, 20)
    QTest.keyClick(selector, Qt.Key.Key_Escape)
    assert cancelled
    selector.close()


def test_overlay_covers_only_text_and_passes_clicks(app):
    image = QImage(400, 160, QImage.Format.Format_RGB32)
    image.fill(QColor('#F0F0F0'))
    overlay = TranslationOverlay(QRect(-400, 30, 200, 80), image,
                                 [TextLine('Hello', QRectF(20, 20, 160, 36), 'Привет')])
    overlay.show()
    app.processEvents()
    rendered = overlay.grab().toImage()
    assert overlay.geometry().x() == -400
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert rendered.pixelColor(190, 70).alpha() == 0
    assert rendered.pixelColor(10, 10).alpha() == 255
    overlay.close()


def test_result_is_shown_and_dismissed_in_place(app):
    page = TranslationPage()
    page.selected_screen = app.primaryScreen()
    page.region = QRect(30, 40, 200, 80)
    page.captured_image = QImage(200, 80, QImage.Format.Format_RGB32)
    page.captured_image.fill(QColor('white'))
    page._result([TextLine('Hello', QRectF(10, 10, 100, 30), 'Привет')])
    assert page.overlay.geometry() == page.region
    assert page.translated.text.toPlainText() == 'Привет'
    assert page.remove_button.isEnabled()
    page.dismiss_overlay()
    assert page.overlay is None
    assert not page.remove_button.isEnabled()
    page.shutdown()
    page.close()


def test_capture_button_is_not_blocked_by_ocr_preflight(app, monkeypatch):
    monkeypatch.setattr(WindowsOCR, 'available', staticmethod(lambda: False))
    page = TranslationPage()
    page.show()
    page.select_button.click()
    assert page._selecting
    assert not page.select_button.isEnabled()
    page._cancel_selection()
    assert page.select_button.isEnabled()
    page.shutdown()
    page.close()


def test_retry_uses_captured_region_and_new_target(app, monkeypatch):
    import eidos.ui.pages.translation as module
    calls = []
    class OCR:
        def recognize(self, image, source):
            calls.append((image.size(), source))
            return [TextLine('Hello', QRectF(10, 10, 100, 30))]
    class Translator:
        def translate(self, text, source, target):
            return target + ': ' + text
    real_worker = module.TranslationWorker
    monkeypatch.setattr(module, 'TranslationWorker',
                        lambda image, source, target, parent: real_worker(
                            image, source, target, parent, ocr=OCR(), translator=Translator()))
    page = TranslationPage()
    page.selected_screen = app.primaryScreen()
    page.region = QRect(30, 40, 200, 80)
    page.captured_image = QImage(200, 80, QImage.Format.Format_RGB32)
    page.captured_image.fill(QColor('white'))
    page.target.setCurrentIndex(page.target.findData('de'))
    page.retry_translation()
    wait_until(app, lambda: page.worker is None)
    assert page.translated.text.toPlainText() == 'de: Hello'
    assert page.retry_button.isEnabled()
    assert page.overlay.geometry() == page.region
    assert calls[0][0] == page.captured_image.size()
    page.shutdown()
    page.close()


def test_real_windows_ocr(app):
    import pytest
    if not WindowsOCR.available():
        pytest.skip('Windows OCR unavailable')
    from eidos.ui.theme import install_font
    install_font()
    image = QImage(700, 160, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    painter.setPen(QColor('black'))
    font = QFont('Inter')
    font.setPixelSize(42)
    painter.setFont(font)
    painter.drawText(25, 70, 'Hello world')
    painter.end()
    results, errors = [], []
    class Translator:
        def translate(self, *_):
            return 'Привет, мир'
    worker = TranslationWorker(image, 'en', 'ru', translator=Translator())
    worker.result.connect(results.append)
    worker.failed.connect(errors.append)
    worker.start()
    wait_until(app, lambda: not worker.isRunning(), timeout=15)
    app.processEvents()
    assert not errors
    assert 'Hello world' in ' '.join(line.text for line in results[0])
    assert results[0][0].rect.x() > 0


def test_source_font_and_multilingual_choices_remain(app):
    from eidos.ui.theme import install_font
    from eidos.ui.screen_translation import source_font
    from eidos.modules.ocr.multilingual import LANGUAGES, MODELS
    install_font()
    assert source_font('Hello world', 36).pixelSize() > source_font('Hello world', 14).pixelSize()
    assert len(LANGUAGES) > 60
    assert all(code in MODELS for code in ['ky', 'ja', 'ar', 'ko'])


def test_static_overlay_reuses_raster(app):
    image = QImage(300, 200, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    line = TextLine('Hello', QRectF(10, 10, 80, 20), 'Привет')
    overlay = TranslationOverlay(QRect(0, 0, 300, 200), image, [line])
    overlay.grab()
    raster = overlay._raster.cacheKey()
    assert not overlay.set_content(image.copy(), [line])
    overlay.grab()
    assert overlay._raster.cacheKey() == raster
    overlay.close()


def test_static_capture_shows_loading_and_finishes(app, monkeypatch):
    import eidos.ui.pages.translation as module
    entered, release = threading.Event(), threading.Event()
    class OCR:
        def recognize(self, *_):
            entered.set()
            release.wait(2)
            return [TextLine('Hello', QRectF(10, 10, 80, 20))]
    class Translator:
        def translate(self, *_):
            return 'Привет'
    real_worker = module.TranslationWorker
    monkeypatch.setattr(module, 'TranslationWorker', lambda image, source, target, parent:
        real_worker(image, source, target, parent, ocr=OCR(), translator=Translator()))
    page = TranslationPage()
    page.selected_screen = app.primaryScreen()
    page.region = QRect(10, 10, 200, 80)
    page.captured_image = QImage(200, 80, QImage.Format.Format_RGB32)
    page.captured_image.fill(QColor('white'))
    page._process_capture()
    wait_until(app, entered.is_set)
    assert not page.loading_widget.isHidden()
    try:
        release.set()
        wait_until(app, lambda: page.worker is None)
        assert page.loading_widget.isHidden()
        assert page.translated.text.toPlainText() == 'Привет'
    finally:
        page.shutdown()
        page.close()
