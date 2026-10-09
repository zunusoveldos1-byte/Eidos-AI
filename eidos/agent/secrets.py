"""Explicit Windows Vault backend; never fall back to plaintext."""
import sys


class SecretStore:
    SERVICE = 'Eidos/assistant'
    NAMES = ('openai', 'telegram', 'discord', 'brave')

    def values(self) -> tuple[str, ...]:
        """Only Eidos credentials, for exact-match redaction; never enumerate Vault."""
        try:
            return tuple(value for name in self.NAMES if (value := self.get(name)))
        except (ImportError, RuntimeError, OSError):
            return ()

    def _backend(self):
        if sys.platform != 'win32':
            raise RuntimeError('Для секретов требуется Windows Credential Manager')
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()

    def get(self, name: str) -> str | None:
        return self._backend().get_password(self.SERVICE, name)

    def set(self, name: str, value: str):
        if not value.strip() or len(value) > 2500:
            raise ValueError('Некорректный секрет')
        self._backend().set_password(self.SERVICE, name, value.strip())

    def delete(self, name: str):
        backend = self._backend()
        if backend.get_password(self.SERVICE, name):
            backend.delete_password(self.SERVICE, name)
