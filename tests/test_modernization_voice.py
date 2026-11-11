from dataclasses import replace
from threading import Event
from types import SimpleNamespace
import json
import sys

import numpy as np
import pytest

from eidos.core.config import AppConfig, ConfigStore
from eidos.modules.voice.stt import WhisperSTT


def test_missing_whisper_model_never_starts_download(monkeypatch, tmp_path):
    calls = []
    class Miss(Exception):
        pass
    def download_model(*a, **kw):
        calls.append(kw['local_files_only'])
        raise Miss()
    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_supported_compute_types=lambda _: {'int8'}))
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=lambda *a, **kw: None))
    monkeypatch.setitem(sys.modules, 'faster_whisper.utils', SimpleNamespace(download_model=download_model))
    monkeypatch.setitem(sys.modules, 'huggingface_hub.errors', SimpleNamespace(LocalEntryNotFoundError=Miss))
    monkeypatch.setattr('huggingface_hub.constants.HF_HUB_CACHE', str(tmp_path / 'absent'))
    with pytest.raises(ValueError, match='локал'):
        WhisperSTT().transcribe(np.ones(16000, np.float32), AppConfig(), tmp_path, lambda *a: None, Event())
    assert calls == [True]


def test_stt_choice_is_saved_and_unknown_choice_rejected(tmp_path):
    config = replace(AppConfig(), stt_engine='vosk', vosk_model_path=str(tmp_path / 'model'))
    store = ConfigStore(tmp_path / 'config.json')
    store.save(config)
    assert store.load() == config
    with pytest.raises(ValueError):
        replace(config, stt_engine='imaginary').validate()


def test_vosk_reuses_model_and_cancels_between_chunks(monkeypatch, tmp_path):
    from eidos.modules.voice.stt import VoskSTT
    (tmp_path / 'am').mkdir()
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'am' / 'final.mdl').touch()
    (tmp_path / 'conf' / 'model.conf').touch()
    loaded, fed = [], []
    cancel = Event()
    class Recognizer:
        def __init__(self, model, rate):
            assert rate == 16000
        def AcceptWaveform(self, data):
            fed.append(len(data))
            return False
        def FinalResult(self):
            return json.dumps({'text': 'открой блокнот'})
    monkeypatch.setitem(sys.modules, 'vosk', SimpleNamespace(Model=lambda path: loaded.append(path), KaldiRecognizer=Recognizer))
    config = replace(AppConfig(), stt_engine='vosk', vosk_model_path=str(tmp_path))
    engine = VoskSTT()
    for _ in range(2):
        assert engine.transcribe(np.ones(16000, np.float32), config, tmp_path, lambda *a: None, cancel) == 'открой блокнот'
    assert len(loaded) == 1
    assert max(fed) <= 8000
    cancel.set()
    assert engine.transcribe(np.ones(16000, np.float32), config, tmp_path, lambda *a: None, cancel) == ''


def test_metrics_are_bounded_and_have_separate_cold_warm_samples():
    from eidos.core.metrics import StageMetrics
    metrics = StageMetrics(capacity=4)
    metrics.observe('stt', 100, cold=True)
    for value in (1, 2, 3, 4, 5):
        metrics.observe('stt', value)
    report = metrics.snapshot()
    assert report['stt']['cold']['p50_ms'] == 100
    assert report['stt']['warm']['count'] == 4
    assert report['stt']['warm']['p95_ms'] > 4


def test_native_vosk_path_uses_ascii_alias_on_windows(monkeypatch, tmp_path):
    from eidos.modules.voice import stt
    path = tmp_path / 'модель'
    monkeypatch.setattr(stt, '_windows_short_path', lambda path: 'C:/EIDOS~1/model')
    assert stt.native_model_path(path, platform='win32') == 'C:/EIDOS~1/model'
    monkeypatch.setattr(stt, '_windows_short_path', lambda path: str(path))
    with pytest.raises(ValueError, match='ASCII'):
        stt.native_model_path(path, platform='win32')


@pytest.mark.parametrize('phrase,value', [('Сделай громкость тридцать процентов', 30),
    ('Установи громкость двадцать пять', 25), ('Сделай громкость ноль процентов', 0),
    ('Сделай громкость сто процентов', 100)])
def test_vosk_spoken_numbers_route_without_llm(phrase, value):
    from eidos.agent.harness import deterministic_call
    assert deterministic_call(phrase) == ('volume', {'mode': 'set', 'value': value})


def test_ambiguous_spoken_number_never_becomes_direct_action():
    from eidos.agent.harness import deterministic_call
    assert deterministic_call('Сделай громкость сто двадцать пять') is None
