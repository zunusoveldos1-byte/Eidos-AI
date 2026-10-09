"""Native Windows end-to-end test: button, screenshot, selection, OCR and online overlay."""
import sys
import faulthandler
import traceback
sys.stdout.reconfigure(encoding='utf-8')
faulthandler.enable()
def report_exception(kind, error, tb):
    traceback.print_exception(kind, error, tb, file=sys.stdout)
    sys.stdout.flush()
sys.excepthook = report_exception
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QTimer, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtTest import QTest
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow

app = QApplication([])
window = MainWindow(ConfigStore(Path('.cache/native-test/config.json')))
window.navigate(3)
sample = QLabel('Hello world')
sample.setWindowTitle('Eidos translation test')
sample.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
sample.setStyleSheet('background: white; color: black; font-family: Inter; font-size: 42px; padding: 25px')
sample.setGeometry(100, 100, 650, 170)
sample.show()
window.show()
page = window.translation
outcome = {'success': False, 'passes': []}

def finish():
    print('STATUS:', page.status.text(), page.feedback.text(), flush=True)
    print('ORIGINAL:', page.original.text.toPlainText(), flush=True)
    print('TRANSLATED:', page.translated.text.toPlainText(), flush=True)
    outcome['success'] = page.overlay is not None and 'Hello' in page.original.text.toPlainText()
    if outcome['success']:
        outcome['passes'].append(page.translated.text.toPlainText())
        if len(outcome['passes']) == 1:
            page.dismiss_overlay()
            page.target.setCurrentIndex(page.target.findData('de'))
            page.retry_button.click()
            page.worker.finished.connect(lambda: QTimer.singleShot(300, finish))
            return
    if page.overlay:
        page.overlay.grab().save('docs/native-translation-overlay.png')
    page.dismiss_overlay()
    sample.close()
    window.close()

def select():
    print('SELECTORS:', len(page.selectors), 'VISIBLE:', [s.isVisible() for s in page.selectors], flush=True)
    if not page.selectors:
        finish()
        return
    selector = next(s for s in page.selectors if s.screen.geometry().contains(sample.geometry().center()))
    origin = selector.screen.geometry().topLeft()
    print('GEOMETRY:', selector.screen.geometry(), selector.geometry(), 'PIXMAP:', selector.snapshot.size(), 'SAMPLE:', sample.geometry(), sample.isVisible(), flush=True)
    rect = sample.geometry().adjusted(5, 5, -5, -5)
    QTest.mousePress(selector, Qt.MouseButton.LeftButton, pos=rect.topLeft() - origin)
    print('PRESSED', flush=True)
    QTest.mouseMove(selector, rect.bottomRight() - origin)
    print('MOVED', flush=True)
    QTest.mouseRelease(selector, Qt.MouseButton.LeftButton, pos=rect.bottomRight() - origin)
    print('RELEASED', flush=True)
    if hasattr(page, 'captured_image'):
        page.captured_image.save('docs/native-translation-input.png')
    if page.worker:
        page.worker.finished.connect(lambda: QTimer.singleShot(300, finish))
    else:
        finish()

def start():
    sample.raise_()
    page.source.setCurrentIndex(page.source.findData('en'))
    page.select_button.click()
    QTimer.singleShot(800, select)

QTimer.singleShot(600, start)
QTimer.singleShot(30000, finish)
app.exec()
print('SUCCESS:', outcome['success'], flush=True)
print('PASSES:', outcome['passes'], flush=True)
raise SystemExit(0 if outcome['success'] else 1)
