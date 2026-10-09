"""Run with python -m eidos."""

import argparse
import sys
import importlib.util
import os
from pathlib import Path


def main() -> int:
    # A downloaded checkout may be launched with global Python while its OCR
    # dependencies live in the project's environment. Use that prepared runtime.
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.venv' / 'Scripts' / 'python.exe'
    ocr_package = root / '.venv' / 'Lib' / 'site-packages' / 'winrt' / 'windows' / 'media' / 'ocr' / '__init__.py'
    missing_ocr = any(importlib.util.find_spec(name) is None for name in ('winrt', 'tesserocr', 'PIL'))
    if (sys.platform == 'win32' and missing_ocr
            and runtime.exists() and ocr_package.exists()
            and Path(sys.executable).resolve() != runtime.resolve()):
        os.execv(str(runtime), [str(runtime), '-m', 'eidos', *sys.argv[1:]])
    parser = argparse.ArgumentParser(description='Eidos — голосовой настольный ассистент')
    parser.add_argument('--smoke-test', action='store_true', help='Открыть окно и безопасно закрыть через 1 секунду, без записи')
    parser.add_argument('--page', choices=['home', 'voice', 'gestures', 'translation', 'settings', 'assistant'], default='home')
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
    window.navigate(['home', 'voice', 'gestures', 'translation', 'settings', 'assistant'].index(args.page))
    window.show()
    if args.smoke_test:
        QTimer.singleShot(1000, window.close)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
