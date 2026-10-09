"""Exercise real Windows OCR and, optionally, a harmless online translation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QFont, QColor, QPainter
from eidos.modules.ocr.engine import WindowsOCR, OnlineTranslator
from eidos.ui.theme import install_font

app = QApplication([])
install_font()
image = QImage(700, 160, QImage.Format.Format_RGB32)
image.fill(QColor('white'))
painter = QPainter(image)
painter.setPen(QColor('black'))
font = QFont('Inter')
font.setPixelSize(42)
painter.setFont(font)
painter.drawText(25, 70, 'Hello world')
painter.end()
image.save(str(Path(__file__).resolve().parents[1] / 'docs' / 'ocr-check.png'))
# Qt initializes COM on the GUI thread; OCR uses MTA in a worker, as in Eidos.
with ThreadPoolExecutor(max_workers=1) as executor:
    lines = executor.submit(WindowsOCR().recognize, image, 'en').result()
print([(line.text, line.rect.getRect()) for line in lines])
assert any('Hello' in line.text for line in lines)
if '--online' in sys.argv:
    print(OnlineTranslator().translate('Hello world', 'en', 'ru'))
