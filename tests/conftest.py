"""Unit tests use no credentials from the interactive user's Windows Vault."""
import pytest


@pytest.fixture(autouse=True)
def no_native_credentials(monkeypatch):
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.get', lambda self, name: None)
