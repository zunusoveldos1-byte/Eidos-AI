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
    stt_engine: str = 'whisper'
    vosk_model_path: str = ''
    device: str = 'cpu'
    speak: bool = True
    tts_voice: str = 'ru-RU-SvetlanaNeural'
    always_on_top: bool = False
    startup_enabled: bool = False
    ui_language: str = 'ru'
    theme: str = 'dark'
    accent_color: str = '#25E6A1'
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
    start_in_tray: bool = False
    mascot_hidden: bool = False
    mascot_app_x: int = 20
    voice_hotkey_enabled: bool = True
    voice_hotkey: str = 'Ctrl+Alt+V'
    floating_enabled: bool = False
    floating_pinned: bool = True
    floating_x: int = 80
    floating_y: int = 80
    reduce_animations: bool = False
    sidebar_collapsed: bool = False
    tts_provider: str = 'edge'
    tts_rate: int = 0
    tts_volume: int = 80
    sapi_voice: str = ''
    voice_response_brief: bool = True
    wake_word_enabled: bool = False
    wake_keyword_path: str = ''
    wake_model_path: str = ''
    wake_sensitivity: float = 0.5
    communication_style: str = 'neutral'
    voice_sensitivity: float = 0.5
    voice_max_seconds: int = 30
    continuous_listening: bool = False
    gesture_camera: str = ''
    gesture_hand: str = 'Right'
    gesture_mirror: bool = True
    gesture_overlay: bool = True
    gesture_mode: str = 'auto'
    gesture_fps: int = 15
    gesture_width: int = 640
    gesture_height: int = 480
    gesture_sensitivity: float = 1.
    gesture_smoothing: float = .3
    gesture_pinch_min: float = .15
    gesture_pinch_max: float = 1.5
    gesture_volume_dead: float = 2.
    gesture_volume_interval: float = .1
    gesture_hold: float = .5
    gesture_cooldown: float = 1.2
    gesture_monitor: str = ''
    gesture_emergency_hotkey: str = 'Ctrl+Alt+G'

    def validate(self) -> None:
        import re
        if (type(self.startup_enabled) is not bool or self.ui_language not in ('ru', 'en', 'ky', 'uz', 'kk')
                or self.theme not in ('dark', 'light') or not isinstance(self.accent_color, str)
                or not re.fullmatch(r'#[0-9a-fA-F]{6}', self.accent_color)):
            raise ValueError('Некорректные настройки запуска, языка или темы.')
        if self.stt_engine not in ('whisper', 'vosk') or not isinstance(self.vosk_model_path, str):
            raise ValueError('Некорректный движок распознавания или путь Vosk.')
        if self.gesture_hand not in ('Right','Left') or self.gesture_mode not in ('auto','volume','media','cursor'):
            raise ValueError('Неизвестный режим или ведущая рука')
        for name in ('gesture_camera','gesture_monitor','gesture_emergency_hotkey'):
            if not isinstance(getattr(self,name),str): raise ValueError('Ожидалась строка: '+name)
        for name in ('gesture_mirror','gesture_overlay'):
            if type(getattr(self,name)) is not bool: raise ValueError('Некорректный переключатель: '+name)
        for name,low,high in [('gesture_fps',5,30),('gesture_width',320,1920),('gesture_height',240,1080),
                              ('gesture_sensitivity',.5,2),('gesture_smoothing',.05,1),
                              ('gesture_pinch_min',.01,2),('gesture_pinch_max',.1,4),
                              ('gesture_volume_dead',.1,10),('gesture_volume_interval',.05,1),
                              ('gesture_hold',.2,2),('gesture_cooldown',.5,3)]:
            value=getattr(self,name)
            if type(value) not in (int,float) or not low<=value<=high:
                raise ValueError('Некорректная настройка жестов: '+name)
        if any(type(getattr(self,n)) is not int for n in ('gesture_width','gesture_height','gesture_fps')):
            raise ValueError('Размер кадра и FPS должны быть целыми')
        if self.gesture_pinch_max-self.gesture_pinch_min < .1:
            raise ValueError('Диапазон расстояния пальцев слишком мал')
        if self.communication_style not in ('neutral', 'friendly', 'energetic'):
            raise ValueError('Неизвестный характер общения')
        if type(self.voice_sensitivity) not in (float, int) or not 0 <= self.voice_sensitivity <= 1:
            raise ValueError('Чувствительность речи должна быть от 0 до 1')
        if type(self.voice_max_seconds) is not int or not 5 <= self.voice_max_seconds <= 120:
            raise ValueError('Длительность команды: от 5 до 120 секунд')
        for name in ('close_to_tray', 'start_in_tray', 'mascot_hidden', 'voice_hotkey_enabled', 'floating_enabled', 'floating_pinned',
                     'reduce_animations', 'sidebar_collapsed', 'voice_response_brief', 'wake_word_enabled'):
            if type(getattr(self, name)) is not bool:
                raise ValueError('Некорректный переключатель: ' + name)
        for name, lower, upper in [('tts_rate', -50, 100), ('tts_volume', 0, 100),
                                   ('floating_x', -100000, 100000), ('floating_y', -100000, 100000)]:
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError('Некорректное значение: ' + name)
        if type(self.mascot_app_x) is not int or not 0 <= self.mascot_app_x <= 100000:
            raise ValueError('Некорректное положение маскота в приложении')
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
        from .shortcuts import parse_shortcut
        emergency=parse_shortcut(self.gesture_emergency_hotkey)
        if emergency is None: raise ValueError('Назначьте клавишу аварийного отключения жестов')
        for shortcut in configured_shortcuts(self).values():
            if shortcut and (shortcut.modifiers,shortcut.key)==(emergency.modifiers,emergency.key):
                raise ValueError('Аварийная клавиша жестов совпадает с другой командой Eidos')
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
            # These keys were previously assignable to global actions. Rebind
            # just conflicting keys on upgrade rather than discard the profile.
            from .shortcuts import ACTIONS, parse_shortcut
            rebound = False
            defaults = AppConfig()
            shortcut_fields = [field for field, _ in ACTIONS.values()] + ['gesture_emergency_hotkey']
            previous = {name: parse_shortcut(content.get(name, getattr(defaults, name)), allow_reserved=True)
                        for name in shortcut_fields}
            reserved = {(2, ord('B')), (2, ord('8'))}
            used = {(key.modifiers, key.key) for key in previous.values()
                    if key and (key.modifiers, key.key) not in reserved}
            for name, shortcut in previous.items():
                if shortcut and shortcut.modifiers == 2 and shortcut.key in (ord('B'), ord('8')):
                    candidates = [getattr(defaults, name)] + [f'Ctrl+Alt+Shift+F{i}' for i in range(1, 12)]
                    for candidate in candidates:
                        key = parse_shortcut(candidate)
                        identity = key.modifiers, key.key
                        if identity not in used:
                            content[name] = key.text
                            used.add(identity)
                            break
                    rebound = True
            config = AppConfig(**{key: value for key, value in content.items() if key in names})
            config.validate()
            if rebound:
                self.warning = 'Ctrl+B и Ctrl+8 используются интерфейсом Eidos. Конфликтующие глобальные клавиши переназначены; остальные настройки сохранены.'
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
