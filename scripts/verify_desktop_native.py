"""Opt-in Windows smoke verification; never locks, shuts down or closes apps."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['QT_QPA_PLATFORM'] = 'windows'
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from eidos.ui.desktop_commands import DesktopUI
from eidos.desktop.windows import WindowsBackend
from eidos.desktop.applications import ApplicationCatalog, checked_executable
from eidos.desktop.session import SessionStore
from eidos.agent.settings import AgentSettings
from eidos.agent.harness import TaskContext
from eidos.agent.tools import audio


def main():
    app = QApplication([])
    ui = DesktopUI.__new__(DesktopUI)
    # capture uses only QApplication, no window or agent state.
    results = {}
    for mode in ('primary', 'all'):
        image = DesktopUI.capture(ui, mode)
        app.clipboard().setImage(image)
        copied = app.clipboard().image()
        results['screenshot_' + mode] = {'ok': not copied.isNull(), 'size': [copied.width(), copied.height()]}
    try:
        current = audio({}, TaskContext(), status=True).text
        # Exercise Core Audio write/read without changing the user's level.
        import re
        value = int(re.search(r'\d+', current)[0])
        result = audio({'mode': 'set', 'value': value}, TaskContext())
        results['audio'] = {'ok': result.verified}
    except Exception as exc:
        results['audio'] = {'ok': False, 'error_type': type(exc).__name__}
    backend = WindowsBackend()
    try:
        backend.launch('https://example.com/')
        results['browser'] = {'ok': True, 'meaning': 'Windows accepted HTTPS launch; page loading not asserted'}
    except OSError as exc:
        results['browser'] = {'ok': False, 'error_type': type(exc).__name__}
    try:
        catalog = ApplicationCatalog(AgentSettings(), backend)
        value = catalog.open('Блокнот')
        results['application'] = {'ok': bool(value)}
        QTest.qWait(1500)
        results['application']['window_found'] = any(row['name'].casefold() == 'notepad' for row in backend.windows())
        executable = checked_executable(Path(os.environ['WINDIR']) / 'System32/notepad.exe')
        # Isolated session with one explicitly verified app, no private window metadata.
        scoped = SimpleNamespace(windows=lambda: [{'path': executable, 'name': 'notepad'}], launch=backend.launch)
        store = SessionStore(Path(__file__).resolve().parents[1] / '.cache/native-desktop/session.json', scoped)
        store.save()
        results['session_restore'] = {'ok': True, 'summary': store.restore(TaskContext()), 'mode': 'already-running skip'}
        # Verify a launch request from the stored session without killing an existing app.
        scoped.windows = lambda: []
        results['session_launch'] = {'ok': True, 'summary': store.restore(TaskContext())}
    except Exception as exc:
        results['application'] = {'ok': False, 'error_type': type(exc).__name__}
    output = Path(__file__).resolve().parents[1] / 'docs/audit-2026-10-13/checks/desktop-native.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__': main()
