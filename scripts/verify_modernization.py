"""Capture current pages/languages using disposable state and no credentials."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['EIDOS_SKIP_ONBOARDING'] = '1'
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.core import i18n
from eidos.ui.main_window import MainWindow
from eidos.core.instance import SingleInstance


def main():
    SecretStore.get = lambda *args: None
    output = ROOT / 'docs/screenshots/modernization'
    output.mkdir(parents=True, exist_ok=True)
    store = ConfigStore(ROOT / '.cache/modernization-ui-verification/config.json')
    store.save(replace(AppConfig(), speak=False, voice_hotkey_enabled=False,
                       translation_hotkeys_enabled=False, close_to_tray=False))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    lock_root = ROOT / '.cache/modernization-instance-verification'
    first, second = SingleInstance(lock_root), SingleInstance(lock_root)
    activated = []
    first.activated.connect(lambda: activated.append(True))
    assert first.acquire() and not second.acquire()
    QTest.qWait(120)
    activation = first.activation_available
    assert not activation or activated, 'Second instance did not activate first window'
    first.close()
    assert second.acquire()
    second.close()
    window = MainWindow(store)
    window.resize(1200, 800)
    window.show()
    QTest.qWait(300)
    rows = []
    missing_sources = {}
    original_key = i18n.key
    def remember_key(source):
        ident = original_key(source)
        missing_sources[ident] = source
        return ident
    i18n.key = remember_key
    try:
        for code in i18n.LANGUAGES:
            window.config = replace(window.config, ui_language=code)
            window._apply_preferences()
            store.save(window.config)
            assert store.load().ui_language == code
            for page, name in ((0, 'home'), (3, 'screen'), (2, 'camera'), (6, 'tools'), (4, 'settings')):
                window.navigate(page)
                QTest.qWait(60)
                assert window.grab().save(str(output / f'{code}-{name}.png'))
                rows.append({'language': code, 'page': name,
                             'navigation': [b.accessibleName() for b in window.sidebar.buttons]})
            for index in range(window.settings.tabs.count()):
                window.settings.tabs.setCurrentIndex(index)
                QTest.qWait(40)
                window.grab().save(str(output / f'{code}-settings-{index}.png'))
        window.config = replace(window.config, ui_language='en', theme='light', accent_color='#548DFF')
        window._apply_preferences()
        window.navigate(4)
        window.settings.tabs.setCurrentIndex(0)
        QTest.qWait(60)
        window.grab().save(str(output / 'en-settings-light.png'))
    finally:
        window.request_exit()
        for _ in range(600):
            if window._allow_close:
                break
            QTest.qWait(10)
        assert window._allow_close, 'Background threads did not stop'
    report = {'pages': rows, 'catalogue_coverage': i18n.coverage(),
              'runtime_missing': i18n.missing(), 'missing_sources': missing_sources,
              'local_activation_available': activation,
              'single_instance_lock': True, 'activation_received': bool(activated), 'clean_shutdown': True,
              'limitations': 'Offscreen captures; microphone/camera acquisition and registered OS hotkey were not activated.'}
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'pages'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
