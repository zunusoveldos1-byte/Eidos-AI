from dataclasses import replace
from threading import Event
from types import SimpleNamespace

import pytest
from eidos.core.config import AppConfig
from eidos.modules.voice.intents import stop_input_intent
from eidos.modules.voice.latched import LatchedInput, RecognizedSpeech
from eidos.modules.voice.worker import VoiceWorker
from test_ui import app, wait_until


@pytest.mark.parametrize('text', ['Отключайся!', 'Эйдос, отключайся', 'Стоп', 'Выключи микрофон'])
def test_exact_stop_commands(text):
    assert stop_input_intent(text)
    assert not stop_input_intent('Объясни, что означает слово отключайся')


def test_recognized_stop_never_calls_model_or_tts(app, tmp_path):
    worker = VoiceWorker()
    called = []
    worker.commands = SimpleNamespace(handle=lambda text: pytest.fail('Stop must be local'))
    worker.input_stop_requested.connect(lambda: called.append(True))
    worker.run_audio(AppConfig(), tmp_path, RecognizedSpeech('Отключайся', 20), 'stop-1', False)
    assert called == [True]


def test_latched_input_keeps_recognizing_until_explicit_stop(app, tmp_path):
    class Capture:
        speech_ended_at = None
        closed = False
        def configure(self, config): assert config.continuous_listening
        def record(self, device, stop, cancel, started):
            started()
            if not entered.is_set():
                entered.set()
                return object()
            cancel.wait(2)
            return None
        def close(self): self.closed = True
    entered = Event()
    capture = Capture()
    engine = SimpleNamespace(begin_stream=lambda *args: True,
        feed=lambda *args: None, finish_stream=lambda cancel: 'Привет')
    listener = LatchedInput(replace(AppConfig(), stt_engine='vosk', continuous_listening=True),
        tmp_path, recorder=capture, stt=SimpleNamespace(select=lambda c: engine))
    texts = []
    listener.recognized.connect(texts.append)
    try:
        listener.start()
        wait_until(app, lambda: texts)
        assert texts[0].text == 'Привет' and listener.isRunning()
    finally:
        listener.stop()
        wait_until(app, lambda: not listener.isRunning())
    assert capture.closed


def test_stop_word_works_during_tts_and_navigation_does_not_unlatch(app, tmp_path, monkeypatch):
    from eidos.core.config import ConfigStore
    from eidos.ui.main_window import MainWindow
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        background = window.background
        background.timer.stop()
        background.listen_enabled = True
        background.paused = False
        stopped = []
        background.latch = SimpleNamespace(stop=lambda: stopped.append(True), isRunning=lambda: False)
        monkeypatch.setattr(background, '_try_voice', lambda: None)
        window.navigate(2)
        assert background.listen_enabled and not background.paused
        submitted = []
        monkeypatch.setattr(window.controller, 'start_audio', lambda *args, **kw: submitted.append(True))
        background._latched_text(RecognizedSpeech('Фраза из динамиков', 20, True))
        assert submitted == []
        background.speech._playing = True
        background._latched_text(RecognizedSpeech('Отключайся', 20, True))
        assert not background.listen_enabled and background.paused and stopped
        assert not background.speech.active
    finally:
        background.latch = None
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
