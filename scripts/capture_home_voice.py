"""Visual QA with explicit injected service signals, not a live speech demo."""
import os
import sys
import json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from eidos.agent.secrets import SecretStore
from eidos.core.config import ConfigStore, AppConfig
from eidos.ui.main_window import MainWindow


def main():
    SecretStore.get = lambda *args: None
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    store = ConfigStore(Path('.cache/home-voice-capture/config.json'))
    store.save(AppConfig(speak=False, voice_hotkey_enabled=False, translation_hotkeys_enabled=False))
    output = Path('docs/screenshots/home-voice')
    output.mkdir(parents=True, exist_ok=True)
    window = MainWindow(store)
    window.resize(1320, 800)
    window.show()
    QTest.qWait(350)
    window.navigate(0)
    bg, orb = window.background, window.voice.mascot
    try:
        for state in ('off', 'active', 'sleep', 'error'):
            bg.paused = state in ('off', 'sleep')
            bg.sleeping = state == 'sleep'
            bg.status('ready', '')
            window.controller.microphone_changed.emit('error' if state == 'error' else 'enabled' if state == 'active' else 'inactive', 'Permission denied' if state == 'error' else '')
            QTest.qWait(260)
            assert orb.ui_state == state
            assert not window.mascot_stage.isVisible()
            assert not window.voice.response_status.isVisible()
            assert not window.voice.input_level.isVisible()
            assert not orb.visual_timer.isActive()
            window.grab().save(str(output / (state + '.png')))
        bg.paused = bg.sleeping = False
        bg.status('ready', '')
        window.controller.microphone_changed.emit('enabled', '')
        for _ in range(5):
            window.controller.speech_activity.emit(.065, True)
            QTest.qWait(60)
        window.grab().save(str(output / 'voice-activity.png'))
        assert orb.visual_timer.isActive()
        window.controller.speech_activity.emit(0., False)
        QTest.qWait(450)
        assert not orb.visual_timer.isActive()
        frozen = orb.phase
        QTest.qWait(120)
        assert orb.phase == frozen
        metrics = []
        for collapsed in (False, True):
            if collapsed:
                window.menu_button.click()
                QTest.qWait(350)
            for width, height in ((1320, 800), (780, 560)):
                window.resize(width, height)
                QTest.qWait(120)
                assert orb.parentWidget().rect().contains(orb.geometry())
                assert window.home.translate_button.width() == window.home.app_button.width()
                assert window.sidebar.group.button(1) is None
                assert window.home.scroll.horizontalScrollBar().maximum() == 0
                metrics.append({'size': [width, height], 'collapsed': collapsed,
                                'horizontal_scroll': window.home.scroll.horizontalScrollBar().maximum()})
                window.grab().save(str(output / f'size-{width}-{height}-{collapsed}.png'))
        (output / 'verification.json').write_text(json.dumps({'visual_qa_injected_signals': True,
             'silence_freezes_phase': True, 'real_devices_started': False,
             'dpr': window.devicePixelRatioF(), 'layout': metrics}, indent=2), encoding='utf-8')
        print('Four states, voice/silence response and four layouts verified. Signals injected; no real recording.')
    finally:
        window.request_exit()
        for _ in range(400):
            if window._allow_close:
                break
            QTest.qWait(10)
        assert window._allow_close


if __name__ == '__main__':
    main()
