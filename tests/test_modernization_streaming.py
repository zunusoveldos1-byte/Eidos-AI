from dataclasses import replace
from threading import Event
from types import SimpleNamespace
import sys
import numpy as np
from eidos.core.config import AppConfig
from eidos.modules.voice.stt import LocalSTT
from eidos.modules.voice.worker import VoiceWorker


def test_vosk_consumes_audio_during_recording_before_finalization(app, monkeypatch, tmp_path):
    (tmp_path / 'am').mkdir()
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'am' / 'final.mdl').touch()
    (tmp_path / 'conf' / 'model.conf').touch()
    fed = []
    class Recognizer:
        def __init__(self, *args): pass
        def AcceptWaveform(self, pcm):
            fed.append(len(pcm))
            return False
        def FinalResult(self): return '{"text":"привет"}'
    monkeypatch.setitem(sys.modules, 'vosk', SimpleNamespace(Model=lambda path: object(), KaldiRecognizer=Recognizer))
    class Recorder:
        chunk_callback = None
        def configure(self, config): pass
        def record(self, device, stop, cancel, started):
            started()
            self.chunk_callback(np.ones(4000, np.float32))
            assert fed == [8000]
            return np.ones(4000, np.float32)
    recorder = Recorder()
    worker = VoiceWorker(recorder=recorder, stt=LocalSTT())
    texts = []
    progress = []
    worker.progress.connect(lambda state, message: progress.append(state))
    worker.transcript.connect(texts.append)
    worker._run(replace(AppConfig(), stt_engine='vosk', vosk_model_path=str(tmp_path), speak=False), tmp_path)
    assert texts == ['привет']
    assert recorder.chunk_callback is None
    assert fed == [8000]
    assert 'transcribing' in progress
    from eidos.core.state import State, StateMachine
    machine = StateMachine()
    machine.transition(State.STARTING)
    for state in progress:
        machine.transition(State(state))
    assert machine.state == State.TRANSCRIBING

from test_ui import app


def test_vosk_timeout_starts_on_first_audio_not_while_waiting(monkeypatch, tmp_path):
    import eidos.modules.voice.stt as module
    (tmp_path / 'am').mkdir()
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'am' / 'final.mdl').touch()
    (tmp_path / 'conf' / 'model.conf').touch()
    class Recognizer:
        def __init__(self, *args): pass
        def AcceptWaveform(self, pcm): return False
    monkeypatch.setitem(sys.modules, 'vosk', SimpleNamespace(Model=lambda path: object(), KaldiRecognizer=Recognizer))
    clock = [10.]
    monkeypatch.setattr(module, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    engine = module.VoskSTT()
    assert engine.begin_stream(replace(AppConfig(), vosk_model_path=str(tmp_path)),
        tmp_path, lambda *args: None, Event())
    assert engine._deadline is None
    clock[0] = 10000.  # Arbitrarily long idle period before speaking.
    engine.feed(np.ones(320, np.float32), Event())
    assert engine._deadline > clock[0]
