from threading import Event
from types import SimpleNamespace
import sys
import numpy as np
import pytest


def test_vosk_receives_original_pcm_without_float_roundtrip():
    from eidos.modules.voice.stt import VoskSTT
    engine = VoskSTT()
    received = []
    engine._recognizer = SimpleNamespace(AcceptWaveform=lambda data: received.append(data) or False)
    engine._deadline = None
    engine._stream_timeout = 90
    pcm = np.array([-32768, -123, 0, 123, 32767], dtype='<i2').tobytes()
    engine.feed(pcm, Event())
    assert received == [pcm] and received[0] is pcm
    with pytest.raises(ValueError): engine.feed(b'x', Event())


def test_edge_collects_audio_in_memory_never_calls_save(monkeypatch):
    from eidos.modules.voice.tts import EdgeTTS
    from eidos.modules.voice.pcm import PCMAudio
    class Communicate:
        def __init__(self, *args, **kwargs): pass
        async def stream(self):
            yield {'type': 'audio', 'data': b'first'}
            yield {'type': 'WordBoundary', 'text': 'ignored'}
            yield {'type': 'audio', 'data': b'second'}
        async def save(self, *args): pytest.fail('Disk audio is forbidden')
    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(Communicate=Communicate))
    decoded = []
    monkeypatch.setattr(EdgeTTS, '_decode', staticmethod(lambda data: decoded.append(data) or PCMAudio(b'\0\0' * 512)))
    monkeypatch.setattr('tempfile.mkstemp', lambda *a, **kw: pytest.fail('Temporary audio is forbidden'))
    result = EdgeTTS().synthesize('Привет', 'voice', Event())
    assert isinstance(result, PCMAudio) and decoded == [b'firstsecond']


def test_silero_local_cpu_frame_state():
    from eidos.modules.voice.vad import SileroVAD
    vad = SileroVAD()
    frame = b'\0\0' * 512
    probability = vad(frame)
    assert 0 <= probability < .5
    vad.reset()
    assert vad(frame) == pytest.approx(probability)
    with pytest.raises(ValueError): vad(b'\0\0')


def test_raw_capture_fans_out_identical_bytes_to_vad_and_vosk(monkeypatch):
    from eidos.modules.voice.recorder import Recorder
    recorder = Recorder()
    received, classified = [], []
    stop = Event()
    pcm = np.arange(512, dtype='<i2').tobytes()
    class VAD:
        def reset(self): pass
        def __call__(self, data): classified.append(data); return 1.
    recorder.vad = VAD()
    recorder.chunk_callback = received.append
    class Stream:
        active = True
        def __init__(self, **kw):
            assert (kw['samplerate'], kw['channels'], kw['dtype'], kw['blocksize']) == (16000, 1, 'int16', 512)
            self.callback = kw['callback']
        def start(self):
            self.callback(pcm, 512, None, False)
            assert not classified and not received  # callback only queues
            stop.set()
        def abort(self): pass
        def close(self): pass
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream,
        check_input_settings=lambda **kw: None))
    monkeypatch.setattr('tempfile.mkstemp', lambda *a, **kw: pytest.fail('Audio touched disk'))
    result = recorder.record(None, stop, Event(), lambda: None)
    assert result.size == 0 and classified == received == [pcm]
    assert classified[0] is received[0]


def test_overflow_discards_whole_command_and_closes_stream(monkeypatch):
    from eidos.modules.voice.recorder import Recorder
    recorder = Recorder()
    class VAD:
        def reset(self): pass
        def __call__(self, data): return 1.
    recorder.vad = VAD()
    closed = []
    stop = Event()
    class Stream:
        active = True
        def __init__(self, **kw): self.callback = kw['callback']
        def start(self):
            for _ in range(33): self.callback(bytes(1024), 512, None, False)
            stop.set()
        def abort(self): pass
        def close(self): closed.append(True)
    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(RawInputStream=Stream,
        check_input_settings=lambda **kw: None))
    with pytest.raises(OSError, match='Потеря аудиоданных'):
        recorder.record(None, stop, Event(), lambda: None)
    assert closed == [True]
