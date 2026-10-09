import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from eidos.core.config import AppConfig
from eidos.modules.voice.recorder import Recorder, resample
from eidos.modules.voice.worker import VoiceWorker


def test_resample_preserves_duration_and_dtype():
    result = resample(np.ones(48000, dtype=np.float32), 48000)
    assert result.shape == (16000,)
    assert result.dtype == np.float32
    assert np.allclose(result, 1)


def test_empty_and_silent_audio_rejected_before_model_load():
    from eidos.modules.voice.stt import WhisperSTT
    for samples in [np.array([], dtype=np.float32), np.zeros(16000, dtype=np.float32)]:
        with pytest.raises(ValueError, match='пуста|тишину'):
            WhisperSTT().transcribe(samples, AppConfig(), Path('.'), lambda *_: None, threading.Event())


def test_recorder_closes_stream_on_cancellation(monkeypatch):
    closed = []
    cancel = threading.Event()

    class Stream:
        active = True

        def __init__(self, **kwargs):
            self.callback = kwargs['callback']

        def start(self):
            self.callback(np.ones((1600, 1), dtype=np.float32), 1600, None, False)
            cancel.set()

        def abort(self):
            closed.append('abort')

        def close(self):
            closed.append('close')

    monkeypatch.setitem(sys.modules, 'sounddevice', SimpleNamespace(
        InputStream=Stream, query_devices=lambda *_: {'default_samplerate': 16000},
        check_input_settings=lambda **_: None,
    ))
    audio = Recorder().record(None, threading.Event(), cancel, lambda: None)
    assert audio is None
    assert closed == ['abort', 'close']


class FakeRecorder:
    def record(self, device, stop, cancel, started):
        started()
        return np.ones(16000, dtype=np.float32)


class FakeSTT:
    def transcribe(self, audio, config, cache, progress, cancel):
        progress('loading', 'Загрузка')
        progress('transcribing', 'Распознавание')
        return 'Привет'


def test_worker_full_cycle_without_real_model(tmp_path):
    class TTS:
        def synthesize(self, text, voice, cancel):
            path = tmp_path / 'response.mp3'
            path.write_bytes(b'fake')
            return path

    worker = VoiceWorker(recorder=FakeRecorder(), stt=FakeSTT(), tts=TTS())
    replies, audio, done = [], [], []
    worker.reply.connect(replies.append)
    worker.audio.connect(audio.append)
    worker.finished.connect(lambda: done.append(True))
    worker.run_cycle(AppConfig(), tmp_path)
    assert replies and 'Привет' in replies[0]
    assert audio == [tmp_path / 'response.mp3']
    assert done == [True]


def test_tts_failure_keeps_text_answer(tmp_path):
    class TTS:
        def synthesize(self, *_):
            raise OSError('offline')

    worker = VoiceWorker(recorder=FakeRecorder(), stt=FakeSTT(), tts=TTS())
    replies, errors = [], []
    worker.reply.connect(replies.append)
    worker.error.connect(errors.append)
    worker.run_cycle(AppConfig(), tmp_path)
    assert replies
    assert 'озвучить' in errors[0]


def test_cancel_before_start_never_opens_microphone(tmp_path):
    class RecorderMustNotRun:
        def record(self, *_):
            pytest.fail('Microphone must remain closed')

    worker = VoiceWorker(recorder=RecorderMustNotRun())
    worker.cancel_event.set()
    worker.run_cycle(AppConfig(), tmp_path)


def test_recording_error_finishes_and_can_be_retried(tmp_path):
    class BrokenRecorder:
        def record(self, *_):
            raise OSError('denied')

    worker = VoiceWorker(recorder=BrokenRecorder())
    errors, done = [], []
    worker.error.connect(errors.append)
    worker.finished.connect(lambda: done.append(True))
    worker.run_cycle(AppConfig(), tmp_path)
    assert 'микрофон' in errors[0].lower()
    assert done == [True]
    worker.run_cycle(AppConfig(), tmp_path)
    assert len(errors) == 2
    assert done == [True, True]
