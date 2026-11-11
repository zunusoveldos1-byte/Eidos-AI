"""Actual Qt captures of hover, keyboard focus and static decorative waves."""
import json
import os
from pathlib import Path
import statistics
import sys
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QPointF, QRect, Qt
from PyQt6.QtGui import QEnterEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow


def main():
    SecretStore.get = lambda *args: None
    output = Path('docs/screenshots/wave-hover')
    output.mkdir(parents=True, exist_ok=True)
    store = ConfigStore(Path('.cache/wave-hover-capture/config.json'))
    store.save(AppConfig(voice_hotkey_enabled=False, translation_hotkeys_enabled=False, speak=False))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(store)
    window.resize(1674, 940)
    window.show()
    QTest.qWait(400)
    try:
        window.home.set_animations(False)
        nav = window.sidebar.buttons[3]
        QApplication.sendEvent(nav, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
        QTest.qWait(200)
        assert not nav.toolTip() and nav.hover == 1
        window.grab().save(str(output / 'home-hover.png'))
        nav.setFocus()
        app.processEvents()
        window.grab().save(str(output / 'keyboard-focus.png'))
        canvas = window.home.content
        region = QRect(0, canvas.height() - 220, canvas.width(), 220)
        canvas.grab(region).save(str(output / 'static-waves.png'))
        samples = []
        for frame in range(30):
            canvas.phase = frame * .1
            start = time.perf_counter()
            canvas.grab(region)
            samples.append((time.perf_counter() - start) * 1000)
        canvas.phase = 0.
        report = {'tooltip_empty': not nav.toolTip(), 'hover_ms': nav.animation.duration(),
                  'focus_visible': nav.hasFocus(), 'static_home_timer_stopped': not window.home.motion_timer.isActive(),
                  'wave_grab_median_ms': round(statistics.median(samples), 2),
                  'dpr': window.devicePixelRatioF()}
        (output / 'verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))
    finally:
        window.request_exit()
        for _ in range(400):
            if window._allow_close:
                break
            QTest.qWait(10)
        assert window._allow_close


if __name__ == '__main__':
    main()
