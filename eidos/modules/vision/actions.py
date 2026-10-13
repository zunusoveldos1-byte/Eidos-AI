"""Windows actions. Construct/use/close only in the processing thread."""

import ctypes
from ctypes import wintypes
import sys

from .logic import Monitor


def monitors():
    """Physical display modes avoid mixing Qt logical coordinates with pixels."""
    if sys.platform != "win32":
        return []

    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("DeviceName", wintypes.WCHAR * 32),
            ("DeviceString", wintypes.WCHAR * 128),
            ("StateFlags", wintypes.DWORD),
            ("DeviceID", wintypes.WCHAR * 128),
            ("DeviceKey", wintypes.WCHAR * 128),
        ]

    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", wintypes.WCHAR * 32),
            ("dmSpecVersion", wintypes.WORD),
            ("dmDriverVersion", wintypes.WORD),
            ("dmSize", wintypes.WORD),
            ("dmDriverExtra", wintypes.WORD),
            ("dmFields", wintypes.DWORD),
            ("x", wintypes.LONG),
            ("y", wintypes.LONG),
            ("orientation", wintypes.DWORD),
            ("fixed", wintypes.DWORD),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", wintypes.WCHAR * 32),
            ("dmLogPixels", wintypes.WORD),
            ("bits", wintypes.DWORD),
            ("width", wintypes.DWORD),
            ("height", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("frequency", wintypes.DWORD),
            ("icmMethod", wintypes.DWORD),
            ("icmIntent", wintypes.DWORD),
            ("mediaType", wintypes.DWORD),
            ("ditherType", wintypes.DWORD),
            ("reserved1", wintypes.DWORD),
            ("reserved2", wintypes.DWORD),
            ("panningWidth", wintypes.DWORD),
            ("panningHeight", wintypes.DWORD),
        ]

    user = ctypes.windll.user32
    result = []
    for i in range(32):
        device = DISPLAY_DEVICE()
        device.cb = ctypes.sizeof(device)
        if not user.EnumDisplayDevicesW(None, i, ctypes.byref(device), 0):
            break
        if not device.StateFlags & 1:
            continue
        mode = DEVMODE()
        mode.dmSize = ctypes.sizeof(mode)
        if (
            user.EnumDisplaySettingsExW(device.DeviceName, -1, ctypes.byref(mode), 0)
            and mode.width
            and mode.height
        ):
            result.append(
                Monitor(device.DeviceName, mode.x, mode.y, mode.width, mode.height)
            )
    return result


class WindowsActions:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Системные действия доступны только в Windows")
        self.endpoint = None
        self.com = None
        self.user = ctypes.windll.user32
        self.user.SetPhysicalCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self.user.SetPhysicalCursorPos.restype = wintypes.BOOL

    def _audio(self):
        if self.com is None:
            import comtypes

            comtypes.CoInitialize()
            self.com = comtypes
        if self.endpoint is None:
            from pycaw.pycaw import AudioUtilities

            self.endpoint = AudioUtilities.GetSpeakers().EndpointVolume
        return self.endpoint

    def volume(self):
        return float(self._audio().GetMasterVolumeLevelScalar()) * 100

    def execute(self, action):
        if action.kind == "volume":
            self._audio().SetMasterVolumeLevelScalar(
                max(0, min(1, action.value / 100)), None
            )
            return f"Громкость: {round(self.volume())}%"
        if action.kind == "cursor":
            if not self.user.SetPhysicalCursorPos(*action.value):
                raise OSError("Windows не разрешила перемещение курсора")
            return "Курсор: управление активно"
        if action.kind == "media":
            # SendInput uses the system multimedia virtual key; no inferred player state.
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("vk", wintypes.WORD),
                    ("scan", wintypes.WORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("extra", ctypes.c_size_t),
                ]

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("x", wintypes.LONG),
                    ("y", wintypes.LONG),
                    ("data", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("extra", ctypes.c_size_t),
                ]

            class PAYLOAD(ctypes.Union):
                _fields_ = [("key", KEYBDINPUT), ("mouse", MOUSEINPUT)]

            class INPUT(ctypes.Structure):
                _fields_ = [("type", wintypes.DWORD), ("payload", PAYLOAD)]

            entries = (INPUT * 2)()
            for i in range(2):
                entries[i].type = 1
                entries[i].payload.key.vk = 0xB3
                entries[i].payload.key.flags = 2 if i else 0
            self.user.SendInput.argtypes = [
                wintypes.UINT,
                ctypes.POINTER(INPUT),
                ctypes.c_int,
            ]
            self.user.SendInput.restype = wintypes.UINT
            if self.user.SendInput(2, entries, ctypes.sizeof(INPUT)) != 2:
                raise OSError("Windows не приняла мультимедийную команду")
            return "Отправлена команда паузы/воспроизведения"
        raise ValueError("Неизвестное действие")

    def close(self):
        self.endpoint = None
        if self.com is not None:
            self.com.CoUninitialize()
            self.com = None
