"""Real Qt geometry checks using disposable config and no credentials."""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QScrollArea
from PyQt6.QtTest import QTest
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow


def main():
    SecretStore.get = lambda *args: None
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    store = ConfigStore(ROOT / '.cache/settings-layout-capture/config.json')
    store.save(replace(AppConfig(), voice_hotkey_enabled=False, translation_hotkeys_enabled=False, speak=False))
    window = MainWindow(store)
    output = ROOT / 'docs/screenshots/settings-layout'
    output.mkdir(parents=True, exist_ok=True)
    records = []
    window.show()
    window.navigate(4)
    try:
        for width, height in ((1920, 1080), (1200, 800), (780, 560)):
            window.resize(width, height)
            for index, name in enumerate(('general', 'model', 'connections', 'voice', 'translation')):
                window.settings.tabs.setCurrentIndex(index)
                for sub in (range(2) if index == 3 else range(1)):
                    if index == 3: window.voice.config_tabs.setCurrentIndex(sub)
                    QTest.qWait(60)
                    shot = f'{width}-{height}-{name}-{sub}'
                    window.grab().save(str(output / (shot + '.png')))
                    scrolls = [area for area in window.settings.findChildren(QScrollArea) if area.isVisibleTo(window)]
                    records.append(dict(case=shot, scrolls=[dict(vertical=a.verticalScrollBar().maximum(),
                        horizontal=a.horizontalScrollBar().maximum(), viewport=[a.viewport().width(), a.viewport().height()]) for a in scrolls]))
        window.resize(1200, 800)
        window.settings.tabs.setCurrentIndex(1)
        ui = window.assistant
        ui.provider.setCurrentIndex(ui.provider.findData('openai'))
        QTest.qWait(60)
        window.grab().save(str(output / 'cloud-model.png'))
        window.config = replace(window.config, theme='light')
        window._apply_preferences()
        QTest.qWait(60)
        window.grab().save(str(output / 'light-model.png'))
    finally:
        window.request_exit()
        for _ in range(600):
            if window._allow_close: break
            QTest.qWait(10)
        assert window._allow_close
    (output / 'geometry.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps(records))


if __name__ == '__main__': main()
