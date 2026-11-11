"""Capture the real Qt widgets and verify home layout/motion at the requested DPI."""
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['EIDOS_SKIP_ONBOARDING'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QRawFont
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from eidos.agent.secrets import SecretStore
from eidos.core.config import AppConfig, ConfigStore
from eidos.ui.main_window import MainWindow


def main():
    SecretStore.get = lambda *args: None
    scale = os.environ.get('QT_SCALE_FACTOR', '1')
    output = Path('docs/screenshots/home-refresh')
    if os.environ.get('QT_QPA_PLATFORM') == 'windows':
        output = output / 'native'
    output.mkdir(parents=True, exist_ok=True)
    store = ConfigStore(Path('.cache/home-refresh-capture') / ('config-' + scale + '.json'))
    store.save(AppConfig(voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(store)
    metrics = []
    try:
        window.resize(1674, 940)
        window.show()
        QTest.qWait(450)
        for collapsed in (False, True):
            if collapsed:
                window.menu_button.click()
                QTest.qWait(350)
            for width, height in ((1674, 940), (1200, 800), (780, 560)):
                window.resize(width, height)
                QTest.qWait(350)
                slug = f'{width}-{height}-' + ('collapsed' if collapsed else 'expanded')
                window.grab().save(str(output / f'{slug}-dpi-{scale}.png'))
                page = window.home
                assert window.workspace.y() == 0 and window.pages.y() == 0
                assert window.menu_button.isVisible()
                assert window.menu_button.parentWidget() is (window.workspace if collapsed else window.sidebar)
                assert not window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                assert not window.windowFlags() & Qt.WindowType.FramelessWindowHint
                assert page.scroll.horizontalScrollBar().maximum() == 0
                assert page.content.width() <= page.scroll.viewport().width()
                assert page.isAncestorOf(window.voice.action_button)
                assert page.hero_mascot.pixmap.hasAlphaChannel()
                assert page.hero_mascot.pixmap.toImage().pixelColor(0, 0).alpha() == 0
                metrics.append({'case': slug, 'dpr': window.devicePixelRatioF(),
                                'microphone_width': page.mic_button.width(), 'content_width': page.content.width(),
                                'viewport_width': page.scroll.viewport().width(),
                                'vertical_scroll': page.scroll.verticalScrollBar().maximum()})
        # Persisted state must be restored by a new window, not just a widget toggle.
        window.request_exit()
        for _ in range(400):
            if window._allow_close:
                break
            QTest.qWait(10)
        window = MainWindow(store)
        window.show()
        QTest.qWait(350)
        assert window.sidebar.isHidden() and window.config.sidebar_collapsed
        assert window.menu_button.isVisible() and window.menu_button.parentWidget() is window.workspace
        assert window.menu_button.toolTip() == 'Показать меню'
        font = QFont('Comfortaa')
        font.setPixelSize(32)
        raw = QRawFont.fromFont(font)
        assert raw.familyName() == 'Comfortaa'
        assert all(raw.supportsCharacter(character) for character in 'ПриветяЭйдосЁё')
        # Compare loop endpoints rendered with the particles at a fixed phase.
        phase = window.home.content.phase
        window.home.content.phase = 0.
        window.home.content.grab().save(str(output / f'waves-start-dpi-{scale}.png'))
        window.home.content.phase = phase
        before = window.home._elapsed
        QTest.qWait(200)
        assert window.home._elapsed > before
        window.navigate(6)
        before = window.home._elapsed
        QTest.qWait(200)
        assert window.home._elapsed == before
        window.navigate(0)
        window.showMinimized()
        QTest.qWait(100)
        assert not window.home.motion_timer.isActive()
        report = {'scale': scale, 'layout': metrics, 'restart_restored_menu': True,
                  'transparent_mascot': True, 'local_cyrillic_font': True,
                  'motion_stops_off_home_and_minimized': True}
        (output / f'verification-dpi-{scale}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        window.request_exit()
        for _ in range(400):
            if window._allow_close:
                break
            QTest.qWait(10)
        assert window._allow_close


if __name__ == '__main__':
    main()
