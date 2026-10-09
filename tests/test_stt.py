import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from eidos.core.config import AppConfig
from eidos.modules.voice.stt import WhisperSTT


@pytest.mark.parametrize('cached', [True, False])
def test_model_cache_and_cpu_int8_without_downloading(monkeypatch, tmp_path, cached):
    calls, statuses, constructors = [], [], []
    class CacheMiss(Exception):
        pass

    def download_model(name, *, cache_dir, local_files_only=False):
        calls.append(local_files_only)
        if local_files_only and not cached:
            raise CacheMiss()
        return str(tmp_path / 'model')

    class Model:
        def __init__(self, path, **kwargs):
            constructors.append(kwargs)

        def transcribe(self, samples, **kwargs):
            assert kwargs['language'] == 'ru'
            assert samples.dtype == np.float32
            return iter([SimpleNamespace(text=' Привет ')]), None

    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_supported_compute_types=lambda _: {'int8', 'float32'}))
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Model))
    monkeypatch.setitem(sys.modules, 'faster_whisper.utils', SimpleNamespace(download_model=download_model))
    monkeypatch.setitem(sys.modules, 'huggingface_hub.errors', SimpleNamespace(LocalEntryNotFoundError=CacheMiss))
    engine = WhisperSTT()
    audio = np.ones(16000, dtype=np.float32)
    for _ in range(2):
        assert engine.transcribe(audio, AppConfig(), tmp_path, lambda *args: statuses.append(args), threading.Event()) == 'Привет'
    assert calls == ([True] if cached else [True, False])
    assert constructors == [{'device': 'cpu', 'compute_type': 'int8', 'local_files_only': True}]
    assert any('интернет' in message for _, message in statuses) is (not cached)
