"""Validated single-key translation shortcuts stored in portable Qt notation."""
from dataclasses import dataclass
import ctypes
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence


ACTIONS = {
    'capture': ('translation_capture_hotkey', 'Выделить текст'),
    'repeat': ('translation_repeat_hotkey', 'Обновить эту область'),
    'dismiss': ('translation_dismiss_hotkey', 'Убрать перевод'),
}


@dataclass(frozen=True)
class Shortcut:
    text: str
    modifiers: int
    key: int


def parse_shortcut(text: str) -> Shortcut | None:
    if not isinstance(text, str):
        raise ValueError('Комбинация клавиш должна быть строкой.')
    if not text.strip():
        return None
    sequence = QKeySequence.fromString(text, QKeySequence.SequenceFormat.PortableText)
    if sequence.count() != 1 or sequence.isEmpty():
        raise ValueError('Нужна одна комбинация клавиш, например Ctrl+Alt+T.')
    combination = sequence[0]
    key = combination.key().value
    keyboard_modifiers = combination.keyboardModifiers()
    modifiers = 0
    for qt_modifier, windows_modifier in [(Qt.KeyboardModifier.AltModifier, 1),
            (Qt.KeyboardModifier.ControlModifier, 2), (Qt.KeyboardModifier.ShiftModifier, 4),
            (Qt.KeyboardModifier.MetaModifier, 8)]:
        if keyboard_modifiers & qt_modifier:
            modifiers |= windows_modifier
    function = Qt.Key.Key_F1.value <= key <= Qt.Key.Key_F24.value
    if key == Qt.Key.Key_F12.value:
        raise ValueError('F12 зарезервирована Windows. Выберите другую клавишу.')
    if not function and not modifiers & (1 | 2 | 8):
        raise ValueError('Добавьте Ctrl, Alt или Win к обычной клавише.')
    if keyboard_modifiers & Qt.KeyboardModifier.KeypadModifier:
        keypad = {Qt.Key.Key_Plus.value: 0x6B, Qt.Key.Key_Minus.value: 0x6D,
                  Qt.Key.Key_Asterisk.value: 0x6A, Qt.Key.Key_Slash.value: 0x6F,
                  Qt.Key.Key_Period.value: 0x6E}
        virtual_key = 0x60 + key - 48 if 48 <= key <= 57 else keypad.get(key)
        if virtual_key is None:
            raise ValueError('На цифровом блоке используйте цифру или арифметическую клавишу.')
    elif 65 <= key <= 90 or 48 <= key <= 57:
        virtual_key = key
    elif function:
        virtual_key = 0x70 + key - Qt.Key.Key_F1.value
    else:
        special = {Qt.Key.Key_Space.value: 0x20, Qt.Key.Key_Tab.value: 0x09,
            Qt.Key.Key_Return.value: 0x0D, Qt.Key.Key_Enter.value: 0x0D,
            Qt.Key.Key_Escape.value: 0x1B, Qt.Key.Key_Backspace.value: 0x08,
            Qt.Key.Key_Insert.value: 0x2D, Qt.Key.Key_Delete.value: 0x2E,
            Qt.Key.Key_Home.value: 0x24, Qt.Key.Key_End.value: 0x23,
            Qt.Key.Key_PageUp.value: 0x21, Qt.Key.Key_PageDown.value: 0x22,
            Qt.Key.Key_Left.value: 0x25, Qt.Key.Key_Up.value: 0x26,
            Qt.Key.Key_Right.value: 0x27, Qt.Key.Key_Down.value: 0x28}
        virtual_key = special.get(key)
        if virtual_key is None and sys.platform == 'win32' and 0 < key <= 0xFFFF:
            scanner = ctypes.windll.user32.VkKeyScanW
            scanner.argtypes, scanner.restype = [ctypes.c_wchar], ctypes.c_short
            character = chr(key).lower()[0]
            result = scanner(character)
            if result == -1:
                # A saved Cyrillic shortcut must also load after switching to English.
                user = ctypes.windll.user32
                user.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
                user.GetKeyboardLayoutList.restype = ctypes.c_int
                count = user.GetKeyboardLayoutList(0, None)
                layouts = (ctypes.c_void_p * count)()
                user.GetKeyboardLayoutList(count, layouts)
                user.VkKeyScanExW.argtypes = [ctypes.c_wchar, ctypes.c_void_p]
                user.VkKeyScanExW.restype = ctypes.c_short
                for layout in layouts:
                    result = user.VkKeyScanExW(character, layout)
                    if result != -1:
                        break
            if result != -1:
                virtual_key = result & 0xFF
                scan_modifiers = (result >> 8) & 7
                modifiers |= (4 if scan_modifiers & 1 else 0) | (2 if scan_modifiers & 2 else 0) | (1 if scan_modifiers & 4 else 0)
        if virtual_key is None:
            raise ValueError('Эта клавиша не поддерживается. Используйте букву, цифру или F1–F24.')
    canonical = sequence.toString(QKeySequence.SequenceFormat.PortableText)
    if canonical in {f'Ctrl+{index}' for index in range(1, 7)}:
        raise ValueError('Ctrl+1…Ctrl+6 используются для разделов Eidos.')
    return Shortcut(canonical, modifiers, virtual_key)


def configured_shortcuts(config):
    result, used = {}, set()
    for action, (field, title) in ACTIONS.items():
        shortcut = parse_shortcut(getattr(config, field))
        if shortcut is not None:
            identity = (shortcut.modifiers, shortcut.key)
            if identity in used:
                raise ValueError('Для разных действий назначьте разные комбинации клавиш.')
            used.add(identity)
        result[action] = shortcut
    return result
