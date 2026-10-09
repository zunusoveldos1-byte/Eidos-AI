"""Check real Windows hotkeys while Eidos is minimized, rebinding and collision rollback."""
import sys
import ctypes
from ctypes import wintypes
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtTest import QTest
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow

class KeyboardInput(ctypes.Structure):
    _fields_ = [('key', wintypes.WORD), ('scan', wintypes.WORD), ('flags', wintypes.DWORD),
               ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
class MouseInput(ctypes.Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG), ('data', wintypes.DWORD),
               ('flags', wintypes.DWORD), ('time', wintypes.DWORD), ('extra', ctypes.c_size_t)]
class InputUnion(ctypes.Union):
    _fields_ = [('keyboard', KeyboardInput), ('mouse', MouseInput)]
class Input(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('value', InputUnion)]
send_input = ctypes.windll.user32.SendInput
send_input.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
send_input.restype = wintypes.UINT

def press(function_key):
    keys = [0x11, 0x12, function_key]
    events = [Input(1, InputUnion(keyboard=KeyboardInput(key, 0, 0, 0, 0))) for key in keys]
    events += [Input(1, InputUnion(keyboard=KeyboardInput(key, 0, 2, 0, 0))) for key in reversed(keys)]
    array = (Input * len(events))(*events)
    assert send_input(len(events), array, ctypes.sizeof(Input)) == len(events)

app = QApplication([])
store = ConfigStore(Path('.cache/hotkeys-native/config.json'))
store.save(replace(AppConfig(), translation_capture_hotkey='Ctrl+Alt+F9',
                   translation_repeat_hotkey='Ctrl+Alt+F10', translation_dismiss_hotkey='Ctrl+Alt+F11'))
window = MainWindow(store)
page = window.translation
page.source.setCurrentIndex(page.source.findData('en'))
sample = QLabel('Hello world')
sample.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
sample.setStyleSheet('background: white; color: black; font-family: Inter; font-size: 42px; padding: 25px')
sample.setGeometry(100, 100, 650, 170)
sample.show()
window.showMinimized()
state = {'capture': False, 'custom_capture': False, 'repeat': False, 'dismiss': False, 'conflict': False}
deadline = QTimer()
deadline.setSingleShot(True)

def finish():
    deadline.stop()
    print('RESULT:', state, 'HOTKEYS:', window.hotkeys.message, flush=True)
    window.show()
    sample.close()
    window.close()

def select():
    if not page.selectors:
        print('No selector opened', flush=True)
        finish()
        return
    selector = next(s for s in page.selectors if s.screen.geometry().contains(sample.geometry().center()))
    origin = selector.screen.geometry().topLeft()
    rect = sample.geometry().adjusted(5, 5, -5, -5)
    QTest.mousePress(selector, Qt.MouseButton.LeftButton, pos=rect.topLeft() - origin)
    QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, pos=rect.bottomRight() - origin)
    page.worker.finished.connect(lambda: QTimer.singleShot(200, first_result))

def first_result():
    state['capture'] = page.overlay is not None and 'Привет' in page.translated.text.toPlainText()
    print('MINIMIZED CAPTURE:', state['capture'], flush=True)
    window.navigate(4)
    window.show()
    window.settings.capture_hotkey.setKeySequence(QKeySequence('Ctrl+Alt+F8'))
    window._save_settings()
    assert store.load().translation_capture_hotkey == 'Ctrl+Alt+F8'
    user = window.hotkeys.backend.user
    assert user.RegisterHotKey(None, 0x3000, 3 | 0x4000, 0x78), 'Old key not released'
    user.UnregisterHotKey(None, 0x3000)
    assert user.RegisterHotKey(None, 0x3001, 3 | 0x4000, 0x76)
    window.settings.capture_hotkey.setKeySequence(QKeySequence('Ctrl+Alt+F7'))
    window._save_settings()
    state['conflict'] = store.load().translation_capture_hotkey == 'Ctrl+Alt+F8' and 'занята' in window.settings.feedback.text()
    user.UnregisterHotKey(None, 0x3001)
    window.settings.capture_hotkey.setKeySequence(QKeySequence('Ctrl+Alt+F8'))
    window.showMinimized()
    sample.activateWindow()
    press(0x77)
    QTimer.singleShot(600, custom_capture)

def custom_capture():
    state['custom_capture'] = bool(page.selectors)
    press(0x7A)
    QTimer.singleShot(250, repeat)

def repeat():
    assert not page.selectors
    window.showMinimized()
    sample.setText('Save changes')
    sample.activateWindow()
    press(0x79)
    QTimer.singleShot(150, watch_repeat)

def watch_repeat():
    if page._selecting:
        QTimer.singleShot(150, watch_repeat)
        return
    if page.worker:
        page.worker.finished.connect(lambda: QTimer.singleShot(200, repeated))
    else:
        finish()

def repeated():
    state['repeat'] = (page.overlay is not None and 'Save changes' in page.original.text.toPlainText()
                       and 'Сохран' in page.translated.text.toPlainText())
    press(0x7A)
    QTimer.singleShot(250, dismissed)

def dismissed():
    state['dismiss'] = page.overlay is None
    finish()

def start():
    assert len(window.hotkeys.actions) == 3, window.hotkeys.message
    sample.raise_()
    sample.activateWindow()
    press(0x78)
    QTimer.singleShot(650, select)

deadline.timeout.connect(finish)
deadline.start(30000)
QTimer.singleShot(500, start)
app.exec()
raise SystemExit(0 if all(state.values()) else 1)
