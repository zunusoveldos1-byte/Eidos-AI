"""Controlled native checks; no microphone recording and no personal configuration."""
import os
import sys
import json
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
os.environ['EIDOS_DATA_DIR'] = str(Path('.cache/background-native/data').resolve())
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow

app = QApplication([])
store = ConfigStore(Path('.cache/background-native/config.json'))
store.save(AppConfig(close_to_tray=True, floating_enabled=True, speak=False,
                     translation_hotkeys_enabled=False, voice_hotkey='Ctrl+Alt+F9'))
window = MainWindow(store)
output = Path('docs/screenshots/background')
output.mkdir(parents=True, exist_ok=True)
report = {'microphone_recorded': False, 'wake_word_executed': False,
          'platform': app.platformName(), 'tray_available': window.background.tray_available()}
states = ['ready', 'listening', 'thinking', 'acting', 'speaking', 'error', 'paused']
index = 0

def capture():
    global index
    state = states[index]
    message = {'listening': 'Демонстрация состояния; микрофон не записывается',
               'speaking': 'Общая анимация речи — демонстрация',
               'error': 'Пример ошибки: микрофон отключён'}.get(state, 'Демонстрация состояния')
    window.background.status(state, message)
    window.background.level(0)
    QTimer.singleShot(180, save)

def save():
    global index
    window.background.floating.grab().save(str(output / (states[index] + '.png')))
    index += 1
    if index < len(states):
        capture()
    else:
        window.navigate(4)
        window.settings.scroll.verticalScrollBar().setValue(260)
        window.grab().save(str(output / 'settings.png'))
        window.close()
        report['close_kept_voice_worker'] = window.controller.thread.isRunning() if report['tray_available'] else None
        report['close_hid_window'] = not window.isVisible()
        if report['tray_available']:
            import ctypes
            calls = []
            window.controller.start = lambda config: calls.append(True)
            identifier = next((key for key, action in window.hotkeys.actions.items() if action == 'voice'), None)
            report['voice_hotkey_native_registration'] = window.hotkeys.backend.native and identifier is not None
            if identifier is not None:
                ctypes.windll.user32.PostThreadMessageW(ctypes.windll.kernel32.GetCurrentThreadId(), 0x0312, identifier, 0)
            def after_hotkey():
                report['voice_hotkey_native_message_dispatched'] = bool(calls)
                window.request_exit()
            QTimer.singleShot(250, after_hotkey)
        else:
            window.request_exit()

window.show()
QTimer.singleShot(450, capture)
QTimer.singleShot(12000, window.request_exit)
app.exec()
report.update(exit_completed=window._allow_close,
              voice_worker_stopped=not window.controller.thread.isRunning(),
              agent_worker_stopped=not window.agent_controller.thread.isRunning(),
              speech_worker_stopped=not window.background.speech.is_running,
              hotkeys_released=not window.hotkeys.actions)
(output / 'native-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(0 if all(report[name] for name in ('exit_completed', 'voice_worker_stopped', 'agent_worker_stopped', 'speech_worker_stopped', 'hotkeys_released')) else 1)
