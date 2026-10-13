"""Read Windows' client-area animation preference without changing it."""
import sys


def system_reduced_motion():
    if sys.platform != 'win32':
        return False
    import ctypes
    enabled = ctypes.c_int(1)
    if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
        return not bool(enabled.value)
    return False
