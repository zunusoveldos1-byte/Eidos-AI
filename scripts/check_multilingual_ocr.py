"""Check local OCR on controlled examples in Latin, Cyrillic, Arabic and Japanese."""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFontDatabase, QImage, QColor, QPainter, QFont
from eidos.ui.theme import install_font
from eidos.modules.ocr.multilingual import ScreenOCR

app = QApplication([])
install_font()
for name in ['arial.ttf', 'YuGothR.ttc', 'msgothic.ttc']:
    path = Path('C:/Windows/Fonts') / name
    if path.exists():
        QFontDatabase.addApplicationFont(str(path))
examples = [('de', 'Hallo Welt', 'Inter'), ('ky', 'Салам дүйнө', 'Inter'),
            ('ar', 'مرحبا بالعالم', 'Arial'), ('ja', '日本語の画面', 'Yu Gothic')]
ocr = ScreenOCR()
for language, text, family in examples:
    image = QImage(1100, 180, QImage.Format.Format_RGB32)
    image.fill(QColor('white'))
    painter = QPainter(image)
    font = QFont(family)
    font.setPixelSize(48)
    painter.setFont(font)
    painter.setPen(QColor('black'))
    painter.drawText(30, 100, text)
    painter.end()
    image.save(f'docs/ocr-{language}-check.png')
    with ThreadPoolExecutor(max_workers=1) as executor:
        lines = executor.submit(ocr.recognize, image, language).result()
    output = ' '.join(line.text for line in lines)
    print(language, repr(text), '->', repr(output), flush=True)
    assert ''.join(output.split()) == ''.join(text.split()), f'{language}: incorrect OCR'
    if '--auto' in sys.argv:
        page = QImage(1200, 550, QImage.Format.Format_RGB32)
        page.fill(QColor('white'))
        painter = QPainter(page)
        painter.setFont(font)
        painter.setPen(QColor('black'))
        for index in range(6):
            painter.drawText(30, 70 + index * 70, (text + ' ') * 3)
        painter.end()
        page.save(f'docs/ocr-{language}-auto-check.png')
        automatic = ScreenOCR()
        with ThreadPoolExecutor(max_workers=1) as executor:
            detected = executor.submit(automatic.recognize, page, 'auto').result()
        print('auto', language, automatic.script, [line.text for line in detected[:2]], flush=True)
        assert detected
