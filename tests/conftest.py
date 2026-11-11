"""Unit tests use no credentials from the interactive user's Windows Vault."""
import pytest


@pytest.fixture(autouse=True)
def no_live_desktop_operations(monkeypatch):
    from eidos.desktop.windows import WindowsBackend
    monkeypatch.setattr(WindowsBackend, 'windows', lambda self: [])
    monkeypatch.setattr(WindowsBackend, 'launch', lambda self, value: None)
    monkeypatch.setattr(WindowsBackend, 'desktop', lambda self: None)
    monkeypatch.setattr(WindowsBackend, 'lock', lambda self: None)
    monkeypatch.setattr(WindowsBackend, 'power', lambda self, action: pytest.fail('Real power operation is forbidden in tests'))


@pytest.fixture(autouse=True)
def no_native_credentials(monkeypatch):
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.get', lambda self, name: None)


@pytest.fixture(autouse=True)
def no_live_tts(monkeypatch):
    # GUI tests must never start an actual external TTS request. Tests of
    # synthesis install their own deterministic engine or async _collect stub.
    import sys
    from types import SimpleNamespace
    def offline(*args, **kwargs):
        raise RuntimeError('Online TTS is disabled in automated tests')
    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(Communicate=offline))
