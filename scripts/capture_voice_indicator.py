"""Record the real Qt indicators with labelled, synthetic capture/audio signals."""
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PIL import Image
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow

SecretStore.get = lambda *a: None
output = Path('docs/screenshots/voice-indicator')
output.mkdir(parents=True, exist_ok=True)
store = ConfigStore(Path('.cache/indicator-preview/config.json'))
store.save(AppConfig(voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(store)
window.resize(1080, 800)
window.show()
window.navigate(1)
floating = window.background.floating
floating.show()
QTest.qWait(200)
frames = []
metrics = []


def snapshot(name):
    for suffix, widget in [('main', window), ('compact', floating)]:
        pixmap = widget.grab()
        pixmap.save(str(output / f'{name}-{suffix}.png'))
        metrics.append({'name': name + '-' + suffix, 'logical': [widget.width(), widget.height()],
                        'pixels': [pixmap.width(), pixmap.height()], 'dpr': pixmap.devicePixelRatioF()})


def frame():
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    floating.grab().save(buffer, 'PNG')
    frames.append(Image.open(BytesIO(bytes(buffer.data()))).convert('RGB'))


try:
    floating.set_answer('Демо состояний. Уровни звука синтетические; микрофон не записывается.')
    states = [('enabled', 'ready'), ('waiting', 'ready'), ('recording', 'listening'),
              ('off', 'ready'), ('error', 'error'), ('inactive', 'speaking'), ('inactive', 'paused')]
    for mic, activity in states:
        window.background.status(activity, 'Демонстрация')
        source = 'wake' if mic == 'waiting' else 'manual'
        window.background._microphones = {'manual': ('inactive', ''), 'wake': ('inactive', '')}
        if window.background.paused != (mic == 'off'):
            window.background.toggle_pause()
        window.background._microphone_changed(source, mic if mic != 'off' else 'inactive',
            'Устройство отключено. Подключите микрофон и повторите.' if mic == 'error' else '')
        # Keep microphone and playback animations sourced independently.
        for index in range(18):
            level = .015 + .08 * abs(math.sin(index * .6))
            if activity == 'speaking':
                window.background.speech_level(level)
            elif mic == 'recording':
                window.background.level(level)
            QTest.qWait(100)
            frame()
        snapshot(mic + '-' + activity)
    window.voice.mascot.set_animations(False)
    floating.mascot.set_animations(False)
    window.background.paused = False
    window.background.status('ready', 'Декоративные анимации выключены')
    window.background._microphone_changed('manual', 'waiting', '')
    snapshot('no-animation')
    frames[0].save(str(output / 'indicator.gif'), save_all=True, append_images=frames[1:],
                   duration=100, loop=0)
    (output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'frames': len(frames), 'seconds': len(frames) / 10, 'logical': [floating.width(), floating.height()]}))
finally:
    window.request_exit()
    for _ in range(200):
        if window._allow_close:
            break
        QTest.qWait(10)
    floating.close()
