from dataclasses import replace

from PyQt6.QtCore import QRect, QRectF, QSize
from PyQt6.QtGui import QImage, QColor, QPixmap

from eidos.core.config import AppConfig, ConfigStore
from eidos.core.languages import LANGUAGE_CODES
from eidos.modules.ocr.engine import TextLine
from eidos.modules.ocr.multilingual import LANGUAGES
from eidos.ui.main_window import MainWindow
from eidos.ui.pages.translation import TranslationPage
from eidos.ui.screen_translation import TextTranslationWorker
from test_ui import app, wait_until


def image(color='white'):
    result = QImage(400, 200, QImage.Format.Format_RGB32)
    result.fill(QColor(color))
    return result


def test_saved_languages_and_display_restore_without_extra_writes(app, tmp_path):
    store = ConfigStore(tmp_path / 'config.json')
    config = replace(AppConfig(), translation_source_language='en',
                     translation_target_language='de', translation_show_overlay=False)
    store.save(config)
    window = MainWindow(store)
    try:
        assert window.translation.source.currentData() == 'en'
        assert window.translation.target.currentData() == 'de'
        assert not window.translation.show_overlay.isChecked()
        window.translation.target.setCurrentIndex(window.translation.target.findData('fr'))
        assert store.load().translation_target_language == 'fr'
    finally:
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning())
        app.processEvents()
    assert LANGUAGE_CODES == {code for code, _, _ in LANGUAGES}


def test_card_mode_keeps_results_visible_without_overlay(app):
    page = TranslationPage()
    page.show_overlay.setChecked(False)
    page._result([TextLine('Hello', QRectF(5, 5, 100, 30), 'Привет')])
    assert page.overlay is None
    assert page.translated.text.toPlainText() == 'Привет'
    assert page.copy_translation.isEnabled()
    page.copy_translation.click()
    assert app.clipboard().text() == 'Привет'
    page.shutdown()
    page.close()


def test_edited_text_is_translated_without_repeating_ocr(app, monkeypatch):
    import eidos.ui.pages.translation as module
    calls = []
    class Translator:
        def translate(self, text, source, target):
            calls.append(text)
            return 'Привет'
    real_worker = TextTranslationWorker
    monkeypatch.setattr(module, 'TextTranslationWorker', lambda text, source, target, parent:
        real_worker(text, source, target, parent, translator=Translator()))
    page = TranslationPage()
    page.show_overlay.setChecked(False)
    page._set_source_text('Helo')
    page.original.text.setPlainText('Hello')
    page.retry_button.click()
    wait_until(app, lambda: page.worker is None)
    assert calls == ['Hello']
    assert page.original.text.toPlainText() == 'Hello'
    assert page.translated.text.toPlainText() == 'Привет'
    assert page.loading_widget.isHidden()
    page.shutdown()
    page.close()


def test_paste_text_does_not_start_translation_or_reuse_old_coordinates(app):
    page = TranslationPage()
    page.last_lines = [TextLine('old', QRectF(10, 10, 100, 20), 'старый')]
    app.clipboard().setText('New text from clipboard')
    page.paste_button.click()
    assert page.original.text.toPlainText() == 'New text from clipboard'
    assert page.worker is None
    assert not page.last_lines
    assert page.retry_button.isEnabled()
    page.shutdown()
    page.close()


def test_refresh_captures_new_pixels_in_same_region(app, monkeypatch):
    class Screen:
        def geometry(self):
            return QRect(-400, 0, 400, 200)
        def grabWindow(self, handle):
            return QPixmap.fromImage(image('red'))
    screen = Screen()
    monkeypatch.setattr('eidos.ui.pages.translation.QApplication.screens', lambda: [screen])
    page = TranslationPage()
    page.region = QRect(-350, 20, 100, 40)
    page.captured_image = image()
    processed = []
    monkeypatch.setattr(page, '_process_capture', lambda: processed.append(page.captured_image))
    page._refreshing = page._selecting = True
    page._refresh_region()
    assert page.region == QRect(-350, 20, 100, 40)
    assert processed[0].size() == QSize(100, 40)
    assert processed[0].pixelColor(0, 0) == QColor('red')
    assert not page._selecting
    page.shutdown()
    page.close()


def test_refresh_cancel_prevents_late_capture(app, monkeypatch):
    page = TranslationPage()
    page.region = QRect(20, 20, 100, 40)
    page._refreshing = page._selecting = True
    page._cancel_selection()
    monkeypatch.setattr('eidos.ui.pages.translation.QApplication.screens',
                        lambda: (_ for _ in ()).throw(AssertionError('Capture after cancel')))
    page._refresh_region()
    assert page.captured_image is None
    page.shutdown()
    page.close()
