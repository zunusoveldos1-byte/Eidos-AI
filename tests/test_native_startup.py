import ctypes
from ctypes.wintypes import MSG
from types import SimpleNamespace
from eidos.ui.main_window import MainWindow


def test_native_message_observer_preserves_default_windows_processing():
    snapshots = []
    owner = SimpleNamespace(session_monitor=SimpleNamespace(snapshot=lambda: snapshots.append(True)))
    message = MSG()
    message.message = 0x11  # WM_QUERYENDSESSION
    assert MainWindow.nativeEvent(owner, b'windows_generic_MSG', ctypes.addressof(message)) == (False, 0)
    assert snapshots == [True]
    message.message = 0x218
    message.wParam = 4  # suspend
    assert MainWindow.nativeEvent(owner, b'windows_generic_MSG', ctypes.addressof(message)) == (False, 0)
    assert len(snapshots) == 2
    message.message = 0x05  # resize
    assert MainWindow.nativeEvent(owner, b'windows_generic_MSG', ctypes.addressof(message)) == (False, 0)
    assert len(snapshots) == 2


def test_unknown_native_event_never_dereferences_foreign_pointer():
    owner = SimpleNamespace(session_monitor=SimpleNamespace(snapshot=lambda: None))
    assert MainWindow.nativeEvent(owner, b'other_native_event', 1) == (False, 0)
