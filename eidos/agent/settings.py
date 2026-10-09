from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path
from urllib.parse import urlsplit
import re

from eidos.core.config import ConfigStore, data_dir

PROFESSIONS = ('Программист', 'Дизайнер', 'Photoshop / обработка фото',
               '3D-художник / аниматор', 'Видеомонтажёр', 'Студент',
               'Преподаватель', 'Работа с документами', 'Предприниматель', 'Другое')
REMOTE_PERMISSIONS = ('windows.settings', 'windows.audio', 'windows.apps', 'browser.open')


@dataclass
class AgentSettings:
    provider: str = 'ollama'
    model: str = 'qwen3:4b-instruct-2507-q4_K_M'
    ollama_url: str = 'http://127.0.0.1:11434'
    cloud_model: str = 'gpt-4.1-mini'
    context_size: int = 4096
    memory_enabled: bool = False
    onboarding_done: bool = False
    name: str = ''
    language: str = 'Русский'
    professions: list[str] = field(default_factory=list)
    tasks: str = ''
    timezone: str = 'Asia/Bishkek'
    search_provider: str = 'duckduckgo'
    telegram_enabled: bool = False
    discord_enabled: bool = False
    telegram_users: list[str] = field(default_factory=list)
    telegram_channels: list[str] = field(default_factory=list)
    discord_users: list[str] = field(default_factory=list)
    discord_channels: list[str] = field(default_factory=list)
    remote_permissions: list[str] = field(default_factory=list)
    approved_apps: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        if self.provider not in ('ollama', 'openai') or self.search_provider not in ('duckduckgo', 'bing', 'brave'):
            raise ValueError('Некорректный провайдер')
        url = urlsplit(self.ollama_url)
        if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1') or url.path not in ('', '/') or url.username or url.password or url.query or url.fragment:
            raise ValueError('Ollama должен быть локальным HTTP-сервисом')
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError('Некорректный порт Ollama')
        if type(self.context_size) is not int or not 1024 <= self.context_size <= 8192:
            raise ValueError('Контекст: от 1024 до 8192')
        for key in ('memory_enabled', 'onboarding_done', 'telegram_enabled', 'discord_enabled'):
            if type(getattr(self, key)) is not bool:
                raise ValueError('Ожидался переключатель')
        for key in ('model', 'cloud_model', 'name', 'language', 'tasks', 'timezone'):
            value = getattr(self, key)
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError('Некорректная строка настроек')
        if not self.model.strip() or not self.cloud_model.strip():
            raise ValueError('Укажите модель')
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Неизвестный часовой пояс IANA') from None
        for key in ('professions', 'telegram_users', 'telegram_channels', 'discord_users', 'discord_channels', 'remote_permissions'):
            values = getattr(self, key)
            if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or len(v) > 100 for v in values):
                raise ValueError('Некорректный список')
        if set(self.professions) - set(PROFESSIONS) or set(self.remote_permissions) - set(REMOTE_PERMISSIONS):
            raise ValueError('Неизвестное разрешение / профессия')
        for key in ('telegram_users', 'telegram_channels', 'discord_users', 'discord_channels'):
            if any(not re.fullmatch(r'-?\d{1,22}', ident) for ident in getattr(self, key)):
                raise ValueError('Списки доступа должны содержать числовые ID')
        if not isinstance(self.approved_apps, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in self.approved_apps.items()):
            raise ValueError('Некорректный список приложений')


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / 'agent.json'
        self.warning = ''

    def load(self) -> AgentSettings:
        try:
            values = json.loads(self.path.read_text(encoding='utf-8'))
            names = {f.name for f in fields(AgentSettings)}
            settings = AgentSettings(**{k: v for k, v in values.items() if k in names})
            settings.validate()
            return settings
        except FileNotFoundError:
            return AgentSettings()
        except Exception:
            self.warning = 'Настройки агента повреждены: применены безопасные значения.'
            return AgentSettings()

    def save(self, settings: AgentSettings):
        # ConfigStore's atomic writer only relies on validate + dataclass fields.
        ConfigStore(self.path).save(settings)
