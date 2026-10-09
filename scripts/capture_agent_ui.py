"""Native Qt captures of the new tabs; never records audio or fabricates replies."""
import argparse
import json
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/screenshots/agent')
    parser.add_argument('--width', default=1280, type=int)
    parser.add_argument('--height', default=880, type=int)
    parser.add_argument('--live', action='store_true', help='Снять реальный ответ установленной модели через UI')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    window = MainWindow(ConfigStore(Path('.cache/agent-capture/config.json')))
    window.resize(args.width,args.height)
    window.show()
    # Resize again once Windows has applied the screen's native DPI.
    QTimer.singleShot(100, lambda: window.resize(args.width, args.height))
    window.navigate(5)
    names = ['chat','memory','calendar','skills','connections','model','profile']
    report = []
    benchmark = Path('docs/agent-benchmark.json')
    if benchmark.exists():
        window.assistant.hardware_display.setPlainText(benchmark.read_text(encoding='utf-8'))
    def select(index):
        window.assistant.tabs.setCurrentIndex(index)
        window.assistant.scroll.verticalScrollBar().setValue(0)
        window.assistant.tabs.currentWidget().scroll.verticalScrollBar().setValue(0)
        QTimer.singleShot(250, lambda:capture(index))
    def capture(index):
        pixmap = window.grab()
        pixmap.save(str(output/(names[index]+'.png')))
        page = window.assistant.tabs.currentWidget()
        report.append({'page':names[index],'logical_size':[window.width(),window.height()], 'pixels':[pixmap.width(),pixmap.height()],
                       'dpr':window.devicePixelRatioF(), 'horizontal_scroll':page.scroll.horizontalScrollBar().maximum(),
                       'viewport_width':page.scroll.viewport().width(), 'content_width':page.content.width()})
        if index+1 < len(names):
            select(index+1)
        else:
            # Capture real onboarding form separately, without saving answers.
            window._show_onboarding()
            QTimer.singleShot(250, onboarding)
    def onboarding():
        window._onboarding.grab().save(str(output/'onboarding.png'))
        (output/'metrics.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
        print(json.dumps(report),flush=True)
        window.close()
    def begin():
        if args.live:
            window.assistant.input.setPlainText('Объясни в двух предложениях, чем список Python отличается от кортежа.')
            window.assistant.send.click()
            wait_reply()
        else:
            select(0)
    def wait_reply():
        if window.agent_controller.active:
            QTimer.singleShot(200,wait_reply)
        else:
            select(0)
    QTimer.singleShot(600,begin)
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
