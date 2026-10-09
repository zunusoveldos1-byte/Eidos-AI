"""Validated user preferences."""

from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
import tempfile

MODELS = ('tiny', 'base', 'small', 'medium', 'large-v3')


def data_dir() -> Path:
    override = os.environ.get('EIDOS_DATA_DIR')
    if override:
        return Path(override)
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'Eidos'


@dataclass(frozen=True)
class AppConfig:
    microphone: int | None = None
    microphone_name: str | None = None
    whisper_model: str = 'base'
    device: str = 'cpu'
    speak: bool = True
    tts_voice: str = 'ru-RU-SvetlanaNeural'
    always_on_top: bool = False
    mascot_animation: bool = True
    translation_hotkeys_enabled: bool = True
    translation_capture_hotkey: str = 'Ctrl+Alt+T'
    translation_repeat_hotkey: str = 'Ctrl+Alt+R'
    translation_dismiss_hotkey: str = 'Ctrl+Alt+X'
    translation_source_language: str = 'auto'
    translation_target_language: str = 'ru'
    translation_show_overlay: bool = True
    translation_provider: str = 'google'
    close_to_tray: bool = False
    voice_hotkey_enabled: bool = True
    voice_hotkey: str = 'Ctrl+Alt+V'
    floating_enabled: bool = False
    floating_pinned: bool = True
    floating_x: int = 80
    floating_y: int = 80
    reduce_animations: bool = False
    tts_provider: str = 'edge'
    tts_rate: int = 0
    tts_volume: int = 80
    sapi_voice: str = ''
    voice_response_brief: bool = True
    wake_word_enabled: bool = False
    wake_keyword_path: str = ''
    wake_model_path: str = ''
    wake_sensitivity: float = 0.5

    def validate(self) -> None:
        for name in ('close_to_tray', 'voice_hotkey_enabled', 'floating_enabled', 'floating_pinned',
                     'reduce_animations', 'voice_response_brief', 'wake_word_enabled'):
            if type(getattr(self, name)) is not bool:
                raise ValueError('Некорректный переключатель: ' + name)
        for name, lower, upper in [('tts_rate', -50, 100), ('tts_volume', 0, 100),
                                   ('floating_x', -100000, 100000), ('floating_y', -100000, 100000)]:
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('Некорректное значение: ' + name)
        if self.tts_provider not in ('edge', 'sapi') or self.translation_provider not in ('', 'google'):
            raise ValueError('Неизвестный провайдер')
        if type(self.wake_sensitivity) not in (float, int) or not 0 <= self.wake_sensitivity <= 1:
            raise ValueError('Чувствительность должна быть от 0 до 1')
        for name in ('sapi_voice', 'wake_keyword_path', 'wake_model_path'):
            if not isinstance(getattr(self, name), str):
                raise ValueError('Ожидалась строка: ' + name)
        if self.microphone is not None and (type(self.microphone) is not int or self.microphone < 0):
            raise ValueError('Некорректный номер микрофона')
        if self.microphone_name is not None and not isinstance(self.microphone_name, str):
            raise ValueError('Некорректное имя микрофона')
        if self.whisper_model not in MODELS or self.device not in ('cpu', 'cuda'):
            raise ValueError('Некорректная модель или устройство Whisper')
        if type(self.speak) is not bool or not isinstance(self.tts_voice, str) or not self.tts_voice.strip():
            raise ValueError('Некорректные настройки озвучивания')
        if type(self.always_on_top) is not bool or type(self.mascot_animation) is not bool:
            raise ValueError('Некорректные настройки внешнего вида')
        if type(self.translation_hotkeys_enabled) is not bool:
            raise ValueError('Некорректная настройка горячих клавиш.')
        from .shortcuts import configured_shortcuts
        configured_shortcuts(self)
        from .languages import LANGUAGE_CODES
        if (self.translation_source_language not in LANGUAGE_CODES | {'auto'}
                or self.translation_target_language not in LANGUAGE_CODES
                or type(self.translation_show_overlay) is not bool):
            raise ValueError('Некорректные настройки перевода.')


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / 'config.json'
        self.warning: str | None = None

    def load(self) -> AppConfig:
        self.warning = None
        try:
            content = json.loads(self.path.read_text(encoding='utf-8-sig'))
            if not isinstance(content, dict):
                raise ValueError('Ожидался JSON-объект')
            names = {field.name for field in fields(AppConfig)}
            config = AppConfig(**{key: value for key, value in content.items() if key in names})
            config.validate()
            return config
        except FileNotFoundError:
            return AppConfig()
        except (OSError, ValueError, TypeError):
            self.warning = 'Настройки не прочитаны: применены значения по умолчанию.'
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        config.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(asdict(config), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
