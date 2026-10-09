"""Regression checks for translation and assistant sharing one application."""
import threading

from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QImage

from eidos.core.config import ConfigStore
from eidos.modules.ocr.engine import TextLine
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_close_waits_for_translation_and_agent_and_releases_hotkeys(app, tmp_path, monkeypatch):
    import eidos.ui.pages.translation as module

    entered, release, agent_started = threading.Event(), threading.Event(), threading.Event()

    class OCR:
        def recognize(self, *_):
            entered.set()
            release.wait(5)
            return [TextLine('Hello', QRectF(10, 10, 80, 20))]

    class Translator:
        def translate(self, *_):
            raise AssertionError('Cancelled OCR must not send text')

    real_worker = module.TranslationWorker
    monkeypatch.setattr(module, 'TranslationWorker', lambda image, source, target, parent:
        real_worker(image, source, target, parent, ocr=OCR(), translator=Translator()))
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))

    def respond(text, context):
        agent_started.set()
        while not context.cancel.wait(.01):
            context.check()
        context.check()

    window.agent_service.respond = respond
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.navigate(5)
        assert window.pages.currentWidget() is window.assistant
        assert window._start_agent_task('chat', 'test')
        wait_until(app, agent_started.is_set)
        page = window.translation
        page.show_overlay.setChecked(False)
        page.selected_screen = app.primaryScreen()
        page.region = QRect(10, 10, 200, 80)
        page.captured_image = QImage(200, 80, QImage.Format.Format_RGB32)
        page._process_capture()
        wait_until(app, entered.is_set)
        window.close()
        wait_until(app, lambda: not window.agent_controller.thread.isRunning())
        assert not window._allow_close
        assert page.worker.cancel.is_set()
        assert not window.hotkeys.actions
        release.set()
        wait_until(app, lambda: page.worker is None and window._allow_close)
        assert not window.controller.thread.isRunning()
    finally:
        release.set()
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning()
                   and not window.agent_controller.thread.isRunning()
                   and window.translation.worker is None)
        app.processEvents()
