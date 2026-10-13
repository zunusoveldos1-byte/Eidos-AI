"""Render real Qt windows and a labelled animation demo without user audio/data."""
import argparse
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--scale', default='1')
parser.add_argument('--output', default='docs/screenshots/voice-upgrade')
args = parser.parse_args()
os.environ['QT_SCALE_FACTOR'] = args.scale
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PIL import Image
from eidos.agent.secrets import SecretStore
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow

SecretStore.get = lambda *a: None  # Preview never accesses Windows Vault.
output = Path(args.output) / ('scale-' + args.scale.replace('.', '-'))
output.mkdir(parents=True, exist_ok=True)
app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(ConfigStore(Path('.cache/voice-preview/config.json')))
window.resize(1080, 760)
window.show()
QTest.qWait(300)
metrics = []


def snapshot(name, widget):
    app.processEvents()
    pixmap = widget.grab()
    pixmap.save(str(output / (name + '.png')))
    metrics.append({'name': name, 'logical': [widget.width(), widget.height()],
                    'pixels': [pixmap.width(), pixmap.height()], 'dpr': pixmap.devicePixelRatioF()})


try:
    window.navigate(1)
    window.voice.show_state('idle', 'Нажмите, чтобы начать · Пробел / Enter при фокусе')
    QTest.qWait(150)
    snapshot('voice', window)
    window.navigate(6)
    QTest.qWait(150)
    snapshot('activation', window)
    floating = window.background.floating
    floating.show()
    floating.set_status('ready', 'Нажмите микрофон, чтобы начать')
    QTest.qWait(150)
    snapshot('compact', floating)
    floating.set_status('paused', 'Озвучка на паузе · нажмите, чтобы продолжить')
    snapshot('paused', floating)
    if args.scale == '1':
        frames = []
        floating.set_answer('Демонстрация анимации: уровни синтетические, микрофон не записывается.')
        for state in ('ready', 'listening', 'thinking', 'speaking', 'paused'):
            floating.set_status(state, 'Демо анимации · синтетический уровень')
            for index in range(12):
                floating.set_level(.018 + .09 * abs(math.sin(index * .7)) if state in ('listening', 'speaking') else 0.)
                QTest.qWait(100)
                buffer = QBuffer()
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                floating.grab().save(buffer, 'PNG')
                frames.append(Image.open(BytesIO(bytes(buffer.data()))).convert('RGB'))
        frames[0].save(str(output / 'animation.gif'), save_all=True, append_images=frames[1:],
                       duration=100, loop=0)
    (output / 'metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False))
finally:
    window.request_exit()
    for _ in range(200):
        if window._allow_close:
            break
        QTest.qWait(10)
    floating.close()
