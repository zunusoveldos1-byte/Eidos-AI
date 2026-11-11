from dataclasses import replace
from threading import Event
from types import SimpleNamespace
import sys

import numpy as np

from eidos.core.config import AppConfig
from eidos.modules.voice.recorder import Recorder
from test_ui import app, wait_until


def test_two_vad_phrases_reuse_stream_and_discard_frames_between_turns(monkeypatch):
    from threading import Thread
    from time import sleep
    streams, fed, speech = [], [], []
    class Stream:
        active = False
        def __init__(self, **kw):
            assert kw['blocksize'] == 512 and kw['dtype'] == 'int16'
            assert kw['samplerate'] == 16000 and kw['channels'] == 1
            self.callback = kw['callback']
            self.starts = self.closed = 0
            streams.append(self)
        def start(self):
            self.starts += 1
            self.active = True
        def abort(self): self.active = False
        def close(self): self.closed += 1
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream,
        check_input_settings=lambda **kw: None))
    class VAD:
        def reset(self): pass
        def __call__(self, data): return float(np.max(np.frombuffer(data, dtype='<i2')) > 1000)
    recorder = Recorder()
    recorder.vad = VAD()
    recorder.configure(replace(AppConfig(), continuous_listening=True))
    recorder.chunk_callback = fed.append
    recorder.speech_callback = lambda: speech.append(True)
    def frame(value):
        streams[0].callback(np.full(512, int(value * 32768), dtype='<i2').tobytes(), 512, None, False)
    try:
        for _ in range(2):
            stop, producer_done = Event(), Event()
            def produce():
                for value in [0] * 80 + [.06] * 8 + [0] * 24:
                    frame(value)
                    sleep(.004)
                producer_done.set()
            producer = Thread(target=produce)
            audio = recorder.record(3, stop, Event(), producer.start)
            producer.join(2)
            assert producer_done.is_set() and stop.is_set()
            assert audio.size == 0
            count = len(fed)
            for _ in range(20): frame(.2)
            assert len(fed) == count and recorder._callback is None
        assert len(streams) == 1 and streams[0].starts == 1
        assert streams[0].closed == 0 and len(speech) == 2
        assert any(max(np.frombuffer(chunk, dtype='<i2')) > 1000 for chunk in fed)
    finally:
        recorder.close()
    assert streams[0].closed == 1


def test_idle_persistent_recorder_is_closed_on_worker_thread_shutdown(app, tmp_path):
    from eidos.modules.voice.controller import VoiceController
    from eidos.modules.voice.worker import VoiceWorker
    class Capture:
        closed = 0
        def record(self, *args): return np.ones(16000, np.float32)
        def close(self): self.closed += 1
    recorder = Capture()
    worker = VoiceWorker(recorder=recorder,
        stt=SimpleNamespace(transcribe=lambda *args: 'Привет'))
    controller = VoiceController(tmp_path, worker=worker)
    try:
        controller.start(replace(AppConfig(), speak=False, continuous_listening=True))
        wait_until(app, lambda: not controller.active)
        assert recorder.closed == 0
    finally:
        controller.shutdown()
        wait_until(app, lambda: not controller.thread.isRunning())
    assert recorder.closed >= 1
