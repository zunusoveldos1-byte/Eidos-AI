from pathlib import Path

import pytest

from scripts import local_voice_demo as demo


def test_default_search_finds_existing_huggingface_cache(monkeypatch, tmp_path):
    from faster_whisper import utils
    from huggingface_hub import constants
    from huggingface_hub.errors import LocalEntryNotFoundError
    global_cache = tmp_path / 'hub'
    monkeypatch.setattr(constants, 'HF_HUB_CACHE', str(global_cache))
    calls = []

    def download(model, *, cache_dir, local_files_only):
        assert model == 'base' and local_files_only is True
        calls.append(Path(cache_dir))
        if Path(cache_dir) != global_cache:
            raise LocalEntryNotFoundError('missing')
        return str(global_cache / 'snapshot')

    monkeypatch.setattr(utils, 'download_model', download)
    assert demo.resolve_whisper_cache('base') == global_cache
    assert calls == [Path('.cache/whisper').resolve(), global_cache]


def test_explicit_cache_is_honoured_and_no_network_enabled(monkeypatch, tmp_path):
    from faster_whisper import utils
    calls = []

    def download(model, *, cache_dir, local_files_only):
        calls.append((model, Path(cache_dir), local_files_only))
        return str(tmp_path / 'snapshot')

    monkeypatch.setattr(utils, 'download_model', download)
    assert demo.resolve_whisper_cache('base', tmp_path) == tmp_path
    assert calls == [('base', tmp_path, True)]


def test_missing_model_reports_searched_paths(monkeypatch, tmp_path):
    from faster_whisper import utils
    from huggingface_hub.errors import LocalEntryNotFoundError

    def missing(*args, **kwargs):
        raise LocalEntryNotFoundError('missing')

    monkeypatch.setattr(utils, 'download_model', missing)
    with pytest.raises(RuntimeError, match='--cache') as failure:
        demo.resolve_whisper_cache('base', tmp_path)
    assert str(tmp_path) in str(failure.value)
