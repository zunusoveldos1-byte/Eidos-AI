"""Probe real capture/cancel and invalid-device telemetry; never run STT or save audio."""
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dataclasses import replace
from PyQt6.QtWidgets import QApplication
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow

sys.stdout.reconfigure(encoding='utf-8')
SecretStore.get = lambda *a: None
store = ConfigStore(Path('.cache/native-indicator/config.json'))
store.save(AppConfig(speak=False, voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(store)
observed = []
window.controller.microphone_changed.connect(lambda state, text: observed.append((state, text)))
report = {'audio_saved': False, 'stt_requested': False}


def pump_until(predicate, seconds=6):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    return bool(predicate())


try:
    # Protect the probe from any accidental path into STT.
    class NoSTT:
        def transcribe(self, *args):
            report['stt_requested'] = True
            raise RuntimeError('This probe must cancel before STT')
    window.controller.worker.stt = NoSTT()
    pump_until(lambda: not window.controller.discovering)
    window.controller.start(window.config)
    opened = pump_until(lambda: window.controller.microphone_state in ('enabled', 'recording', 'error'))
    report['real_capture'] = {'settled': opened, 'state': window.controller.microphone_state,
                             'main': window.voice.title.text(),
                             'compact': window.background.floating.microphone_label.text()}
    if opened and window.controller.microphone_state != 'error':
        pump_until(lambda: False, .35)
    window.background.toggle_pause()
    report['mute'] = {'main': window.voice.mascot.microphone_state,
                      'compact': window.background.floating.mascot.microphone_state,
                      'playback_paused': window.controller.playback.paused}
    pump_until(lambda: not window.controller.active)
    window.background.toggle_pause()
    window.controller.start(replace(window.config, microphone=999999))
    pump_until(lambda: window.controller.microphone_state == 'error' and not window.controller.active)
    report['invalid_device'] = {'main': window.voice.mascot.microphone_state,
                                'compact': window.background.floating.mascot.microphone_state,
                                'description': window.voice.operation.text(),
                                'state_after_task_finished': window.controller.microphone_state}
    report['capture_events'] = observed
finally:
    window.request_exit()
    pump_until(lambda: window._allow_close)
    window.background.floating.close()
output = Path('docs/screenshots/voice-indicator/native-report.json')
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
if report['stt_requested'] or report['invalid_device']['main'] != 'error' or report['mute']['main'] != 'off':
    raise SystemExit(1)
