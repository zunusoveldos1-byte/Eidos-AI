"""Synthetic Qt screenshots: no real camera, microphone, OCR or translation."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtCore import QRect, QRectF
from PyQt6.QtGui import QImage, QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from eidos.core.config import AppConfig, ConfigStore
from eidos.agent.secrets import SecretStore
from eidos.modules.ocr.engine import TextLine
from eidos.ui.main_window import MainWindow
from eidos.ui.screen_translation import RegionSelector, TranslationOverlay, OverlayControls


def main():
    SecretStore.get = lambda *a: None
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    store = ConfigStore(ROOT / '.cache/minimal-pages-capture/config.json')
    store.save(replace(AppConfig(), speak=False, voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    window = MainWindow(store)
    output = ROOT / 'docs/screenshots/minimal-pages'
    if os.environ.get('QT_QPA_PLATFORM') == 'windows': output = output / 'native'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'monitors.json').write_text(json.dumps([dict(geometry=s.geometry().getRect(), dpr=s.devicePixelRatio())
        for s in app.screens()], indent=2), encoding='utf-8')
    records = []
    image = QImage(640, 480, QImage.Format.Format_RGB32)
    image.fill(QColor('#264637'))
    painter = QPainter(image)
    painter.setPen(QColor('#25E6A1'))
    painter.drawEllipse(200, 100, 240, 260)
    painter.drawText(230, 230, 'SYNTHETIC FRAME')
    painter.end()
    window.show()
    try:
        for width, height in ((1920,1080), (1200,800), (780,560)):
            window.resize(width,height)
            window.navigate(3)
            QTest.qWait(60)
            window.grab().save(str(output / f'{width}-{height}-translation.png'))
            records.append(dict(case=f'{width}-{height}-translation', vertical=window.translation.scroll.verticalScrollBar().maximum(), horizontal=window.translation.scroll.horizontalScrollBar().maximum()))
            window.navigate(2)
            page = window.gestures
            page.preview.set_image(image)
            page.gesture_status.setText('Жест: Курсор')
            page.metrics.setText('15 FPS | 50 мс')
            page.preview.position_badges()
            for expanded in (False, True):
                page.details_button.setChecked(expanded)
                QTest.qWait(60)
                window.grab().save(str(output / f'{width}-{height}-camera-{int(expanded)}.png'))
                records.append(dict(case=f'{width}-{height}-camera-{int(expanded)}', vertical=page.scroll.verticalScrollBar().maximum(), horizontal=page.scroll.horizontalScrollBar().maximum()))
        selector = RegionSelector(app.primaryScreen(), QPixmap.fromImage(image))
        selector.show()
        QTest.qWait(80)
        selector.grab().save(str(output / 'monitor-neon.png'))
        selector.close()
        translated = TranslationOverlay(QRect(0,0,400,100), image,
            [TextLine('Hello', QRectF(20,20,200,35), 'Привет')])
        translated.show()
        translated.grab().save(str(output / 'translation-layer.png'))
        translated.close()
        controls = OverlayControls(app.primaryScreen())
        controls.show()
        QTest.qWait(80)
        controls.grab().save(str(output / 'translation-controls.png'))
        controls.close()
        controls.deleteLater()
    finally:
        window.request_exit()
        for _ in range(600):
            if window._allow_close: break
            QTest.qWait(10)
        assert window._allow_close
    (output / 'geometry.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps(records))


if __name__ == '__main__': main()
