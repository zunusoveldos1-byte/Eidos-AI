"""Run with python -m eidos."""

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description='Eidos — голосовой настольный ассистент')
    parser.add_argument('--smoke-test', action='store_true', help='Открыть окно и безопасно закрыть через 1 секунду, без записи')
    args = parser.parse_args()
    try:
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from eidos.core.logging import configure_logging
        from eidos.ui.main_window import MainWindow
    except ImportError as exc:
        print(f'Не установлены зависимости интерфейса: {exc}. Выполните python -m pip install -r requirements.txt.', file=sys.stderr)
        return 1
    configure_logging()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Eidos')
    app.setOrganizationName('Eidos')
    window = MainWindow()
    window.show()
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
