"""Regression checks for translation and assistant sharing one application."""
import threading
from dataclasses import replace

import numpy as np

from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QImage

from eidos.core.config import ConfigStore
from eidos.modules.ocr.engine import TextLine
from eidos.ui.main_window import MainWindow
from test_ui import app, wait_until


def test_voice_cancel_allows_restart_while_translation_completes(app, tmp_path, monkeypatch):
    import eidos.ui.pages.translation as module

    recognized, translating, release = threading.Event(), threading.Event(), threading.Event()

    class Recorder:
        def record(self, device, stop, cancel, started):
            started()
            return np.ones(8000, dtype=np.float32)

    class STT:
        calls = 0

        def transcribe(self, audio, config, cache, progress, cancel):
            self.calls += 1
            progress('transcribing', 'Распознавание')
            if self.calls == 1:
                recognized.set()
                cancel.wait(5)
            return 'Привет'

    class Translator:
        def translate(self, text, source, target):
            translating.set()
            release.wait(5)
            return 'Привет, мир'

    worker = module.TextTranslationWorker
    monkeypatch.setattr(module, 'TextTranslationWorker', lambda text, source, target, parent:
        worker(text, source, target, parent, translator=Translator()))
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.controller.worker.recorder = Recorder()
        window.controller.worker.stt = STT()
        assert window._persist(replace(window.config, speak=False))
        window.translation.show_overlay.setChecked(False)
        window.translation.original.text.setPlainText('Hello world')
        window.translation.retry_button.click()
        wait_until(app, translating.is_set)
        wait_until(app, lambda: not window.controller.discovering)
        window.controller.start(window.config)
        wait_until(app, recognized.is_set)
        wait_until(app, lambda: window.controller.machine.state.value == 'transcribing')
        assert window.controller.active and window.translation.is_running
        window.voice.action_button.click()
        wait_until(app, lambda: not window.controller.active)
        assert not window.controller.cancelling
        assert window.voice.action_button.isEnabled()
        assert window.translation.is_running
        # The real UI button must start a second cycle after cancellation.
        window.voice.action_button.click()
        wait_until(app, lambda: window.controller.worker.stt.calls == 2
                   and not window.controller.active)
        assert window.voice.recognized.text.toPlainText() == 'Привет'
        assert 'Привет! Я Eidos' in window.voice.answer.text.toPlainText()
        release.set()
        wait_until(app, lambda: window.translation.worker is None)
        assert window.translation.translated.text.toPlainText() == 'Привет, мир'
        assert 'Привет! Я Eidos' in window.voice.answer.text.toPlainText()
    finally:
        release.set()
        window.close()
        wait_until(app, lambda: not window.controller.thread.isRunning()
                   and not window.agent_controller.thread.isRunning()
                   and window.translation.worker is None)
        app.processEvents()


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
