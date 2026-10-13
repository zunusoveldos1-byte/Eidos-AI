from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
import pytest

from eidos.ui.mascot import Mascot


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


def test_six_emotions_have_distinct_artwork_without_animation(app):
    mascot = Mascot(180)
    mascot.set_animations(False)
    mascot.show()
    images = []
    for state in ('ready', 'listening', 'thinking', 'speaking', 'success', 'error'):
        mascot.set_state(state)
        images.append(mascot.grab().toImage())
    assert all(a != b for index, a in enumerate(images) for b in images[index + 1:])
    mascot.close()


def test_shared_completion_and_error_reach_decorative_mascots(app, tmp_path):
    from eidos.core.config import ConfigStore
    from eidos.ui.main_window import MainWindow
    from test_ui import wait_until

    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        wait_until(app, lambda: not window.controller.discovering)
        window.background._mark_response_completed('Готово')
        window.background.status('idle', 'Готово')
        assert all(m.state == 'success' for m in window.findChildren(Mascot))
        window.background.status('recording', 'Слушаю')
        assert all(m.state == 'listening' for m in window.findChildren(Mascot))
        window.background._mark_response_completed('Ответ')
        window.background.status('error', 'Не удалось выполнить')
        window.background.status('idle', 'Готов')
        assert all(m.state == 'ready' for m in window.findChildren(Mascot))
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)


def test_idle_blinks_using_artwork_and_speech_moves_mouth(app):
    mascot = Mascot(180)
    mascot.show()
    for state, tick in (('ready', 48), ('speaking', 3)):
        mascot.set_state(state)
        mascot._tick = 0
        opened = mascot.grab().toImage()
        mascot._tick = tick
        assert opened != mascot.grab().toImage()
    mascot.close()


def test_celebration_returns_to_idle_and_cannot_override_new_work(app):
    mascot = Mascot()
    mascot.celebrate(duration_ms=30)
    assert mascot.state == 'success'
    QTest.qWait(70)
    assert mascot.state == 'ready'
    mascot.celebrate(duration_ms=30)
    mascot.set_state('listening')
    QTest.qWait(70)
    assert mascot.state == 'listening'
    mascot.close()
