"""Capture actual Qt controls; camera stays off. --scale is for DPI checks."""

import argparse
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--scale", default="1")
args = parser.parse_args()
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = args.scale
os.environ["EIDOS_SKIP_ONBOARDING"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
window = MainWindow(ConfigStore(Path(".cache/gesture-capture/config.json")))
window.resize(1320, 1000)
window.show()
window.navigate(2)
QTest.qWait(800)
output = Path("docs/gestures")
output.mkdir(exist_ok=True)
window.grab().save(str(output / f"page-{args.scale}.png"))
window.gestures.scroll.verticalScrollBar().setValue(
    window.gestures.scroll.verticalScrollBar().maximum()
)
QTest.qWait(100)
window.grab().save(str(output / f"parameters-{args.scale}.png"))
window.request_exit()
for n in range(1000):
    app.processEvents()
    if window._allow_close:
        break
    QTest.qWait(10)
assert window._allow_close
