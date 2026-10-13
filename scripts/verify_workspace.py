"""Isolated layout/DPI probe; never starts physical microphone or camera."""
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['EIDOS_SKIP_ONBOARDING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow
from eidos.ui.mascot import Mascot


def main():
    SecretStore.get = lambda *args: None
    scale = os.environ.get('QT_SCALE_FACTOR', '1')
    root = Path('.cache/workspace-dpi-' + scale)
    store = ConfigStore(root / 'config.json')
    store.save(AppConfig(voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    app = QApplication([])
    window = MainWindow(store)
    try:
        window.show_startup()
        assert window.isMaximized() and not window.isFullScreen()
        QTest.qWait(100)
        window.showNormal()
        window.resize(1000, 760)
        window.placement.to_desktop()
        window.placement.move_character(QPoint(-100000, -100000))
        window.placement.save_position()
        desktop = window.placement.desktop
        assert desktop.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        assert any(screen.availableGeometry().contains(desktop.geometry()) for screen in app.screens())
        frame = desktop.grab()
        assert frame.toImage().pixelColor(0, 0).alpha() == 0
        window.placement.to_app()
        assert len(window.findChildren(Mascot)) == 1
        window.navigate(4)
        QTest.qWait(80)
        output = Path('docs/screenshots/workspace')
        output.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(output / ('dpi-' + scale + '.png')))
        metrics = {'scale': scale, 'dpr': window.devicePixelRatioF(),
                   'logical_size': [window.width(), window.height()],
                   'pixel_size': [window.grab().width(), window.grab().height()],
                   'desktop_transparent_corner': True, 'startup_maximized': True,
                   'character_count': 1, 'physical_monitor_count': len(app.screens()),
                   'note': 'Qt offscreen geometry probe; not a physical multi-monitor test'}
        (output / ('dpi-' + scale + '.json')).write_text(json.dumps(metrics, indent=2), encoding='utf-8')
        print(json.dumps(metrics))
    finally:
        window.request_exit()
        for _ in range(500):
            if window._allow_close:
                break
            QTest.qWait(10)
        assert window._allow_close


if __name__ == '__main__':
    main()
