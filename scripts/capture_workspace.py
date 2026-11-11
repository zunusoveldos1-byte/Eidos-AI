"""Actual Qt page captures and a rendered recording of character transfers.

No physical microphone/camera or external model is started. The animation
composites Qt widget captures onto a labelled stage, not a desktop recording.
"""
from io import BytesIO
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['EIDOS_SKIP_ONBOARDING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QBuffer, QIODevice, QPoint, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PIL import Image
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow


def main():
    SecretStore.get = lambda *args: None
    output = Path('docs/screenshots/workspace')
    output.mkdir(parents=True, exist_ok=True)
    store = ConfigStore(Path('.cache/workspace-capture/config.json'))
    store.save(AppConfig(voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(store)
    window.resize(1320, 920)
    window.show()
    QTest.qWait(200)
    try:
        metrics = []
        for page_id, slug in ((0, 'home'), (1, 'voice'), (3, 'screen'),
                              (2, 'camera'), (6, 'tools'), (4, 'settings')):
            window.navigate(page_id)
            QTest.qWait(80)
            pixmap = window.grab()
            pixmap.save(str(output / (slug + '.png')))
            metrics.append({'page': slug, 'size': [window.width(), window.height()],
                            'dpr': pixmap.devicePixelRatioF()})
        window.navigate(6)
        window.assistant.history.setPlainText('Вы\nОбъясни выбранный текст.\n\nEidos\nЗдесь будет ответ по фактически полученным данным.')
        window.resize(1100, 740)
        frames = []

        def frame(title):
            app.processEvents()
            canvas = QPixmap(1450, 850)
            canvas.fill(QColor('#24392D'))
            painter = QPainter(canvas)
            painter.setPen(QColor('#E9F5EE'))
            painter.drawText(24, 28, 'Демонстрация Qt · ' + title)
            painter.drawText(1150, 70, 'Рабочий стол')
            painter.drawPixmap(20, 50, window.grab())
            if window.placement.desktop.isVisible():
                painter.drawPixmap(1170, 350, window.placement.desktop.grab())
            painter.end()
            data = QBuffer()
            data.open(QIODevice.OpenModeFlag.WriteOnly)
            canvas.save(data, 'PNG')
            frames.append(Image.open(BytesIO(bytes(data.data()))).convert('RGB'))

        window.background.status('playing', 'Демонстрация: ответ продолжается при переносе')
        for index in range(8):
            window.character._animate()
            frame('Персонаж внутри приложения')
        character = window.character
        QTest.mousePress(character, Qt.MouseButton.LeftButton, pos=QPoint(70, 70))
        for index in range(1, 9):
            QTest.mouseMove(character, QPoint(70 + index * 24, 70), delay=20)
            frame('Перетаскивание в выделенной полосе')
        QTest.mouseRelease(character, Qt.MouseButton.LeftButton, pos=QPoint(240, 70))
        window.placement.to_desktop()
        window.placement.desktop.set_answer('Ответ продолжается; персонаж тот же.')
        for index in range(12):
            character._animate()
            frame('На рабочий стол · состояние речи сохранено')
        window.placement.to_app()
        for index in range(8):
            character._animate()
            frame('Вернуть в приложение · тот же персонаж')
        frames[0].save(output / 'mascot-transfer.gif', save_all=True, append_images=frames[1:],
                       duration=130, loop=0, optimize=False)
        window.placement.to_desktop()
        window.placement.desktop.grab().save(str(output / 'desktop-character.png'))
        window.placement.to_app()
        window.resize(800, 600)
        window.navigate(4)
        QTest.qWait(60)
        window.grab().save(str(output / 'settings-small.png'))
        (output / 'captures.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    finally:
        window.request_exit()
        for _ in range(500):
            if window._allow_close:
                break
            QTest.qWait(10)
        if not window._allow_close:
            raise RuntimeError('Workers did not stop')
    print(output.resolve())


if __name__ == '__main__':
    main()
