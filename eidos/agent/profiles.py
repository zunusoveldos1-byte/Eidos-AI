"""Explicit profile selection. Stable hashed directories cannot escape the root."""
from dataclasses import dataclass, field
import hashlib
from eidos.core.config import ConfigStore


@dataclass(frozen=True)
class ProfileSelection:
    active: str = 'Основной'
    names: list[str] = field(default_factory=lambda: ['Основной'])

    def validate(self):
        if (not isinstance(self.active, str) or not isinstance(self.names, list) or
                not self.names or len(self.names) > 50 or self.active not in self.names or
                any(not isinstance(n, str) or not n.strip() or len(n) > 80 for n in self.names)):
            raise ValueError('Имя профиля: от 1 до 80 символов, максимум 50 профилей')


class Profiles:
    def __init__(self, root):
        self.root = root
        self.store = ConfigStore(root / 'profiles.json')
        self.selection = ProfileSelection()
        if self.store.path.exists():
            import json
            try:
                self.selection = ProfileSelection(**json.loads(self.store.path.read_text(encoding='utf-8')))
                self.selection.validate()
            except (ValueError, TypeError, OSError):
                self.selection = ProfileSelection()

    def directory(self, name):
        return self.root if name == 'Основной' else self.root / 'profiles' / hashlib.sha256(name.encode('utf-8')).hexdigest()[:20]

    def select(self, name):
        names = self.selection.names
        selection = ProfileSelection(name, names if name in names else names + [name])
        selection.validate()
        self.store.save(selection)
        self.selection = selection
