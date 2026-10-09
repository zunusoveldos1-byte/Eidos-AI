"""Capture actual native Qt pages. No fake transcripts and no microphone capture."""
import argparse
import json
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from eidos.core.config import ConfigStore
from eidos.ui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='docs/screenshots/normal')
    parser.add_argument('--width', type=int, default=1200)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    window = MainWindow(ConfigStore(Path('.cache/ui-capture/config.json')))
    window.resize(args.width, args.height)
    window.show()
    names = ['home', 'voice', 'gestures', 'translation', 'settings']
    if args.compact:
        window.set_compact(True)
        names = ['compact']
    report = []

    def capture(index: int) -> None:
        page = window.pages.currentWidget()
        pixmap = window.grab()
        pixmap.save(str(output / f'{names[index]}.png'))
        report.append({
            'page': names[index], 'logical_size': [window.width(), window.height()],
            'pixel_size': [pixmap.width(), pixmap.height()],
            'device_pixel_ratio': window.devicePixelRatioF(),
            'content_width': page.content.width(), 'viewport_width': page.scroll.viewport().width(),
            'vertical_scroll': page.scroll.verticalScrollBar().maximum(),
            'horizontal_scroll': page.scroll.horizontalScrollBar().maximum(),
        })
        if index + 1 < len(names):
            select(index + 1)
        else:
            (output / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False))
            window.close()

    def select(index: int) -> None:
        window.navigate(1 if args.compact else index)
        window.pages.currentWidget().scroll.verticalScrollBar().setValue(0)
        QTimer.singleShot(180, lambda: capture(index))

    QTimer.singleShot(500, lambda: select(0))
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
