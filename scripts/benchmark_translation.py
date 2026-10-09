"""Measure overlay rendering using controlled dense UI text; no network or desktop OCR."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import json
import statistics
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtWidgets import QApplication
from eidos.ui.theme import install_font
from eidos.modules.ocr.engine import TextLine
from eidos.ui.screen_translation import TranslationOverlay, source_font

app = QApplication([])
install_font()
image = QImage(1920, 1080, QImage.Format.Format_RGB32)
image.fill(QColor('white'))
lines = [TextLine(f'Settings {index}', QRectF(20 + index % 8 * 235, 20 + index // 8 * 42, 130, 18),
                  f'Настройки {index}') for index in range(192)]
overlay = TranslationOverlay(QRect(0, 0, 1920, 1080), image, lines)
source_font.cache_clear()
timings = []
for _ in range(8):
    started = time.perf_counter()
    overlay.set_content(image, lines)
    overlay.grab()
    timings.append((time.perf_counter() - started) * 1000)
report = {'lines': len(lines), 'cold_render_ms': round(timings[0], 2),
          'unchanged_render_median_ms': round(statistics.median(timings[1:]), 2)}
print(json.dumps(report))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2), encoding='utf-8')
overlay.close()
