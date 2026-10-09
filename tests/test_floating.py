import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6.QtCore import QAbstractAnimation, QPoint, QRect, QSize, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from eidos.ui.mascot import Mascot


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('state', ['ready', 'listening', 'thinking', 'acting', 'speaking', 'error', 'paused'])
def test_mascot_supports_shared_states(app, state):
    mascot = Mascot(100)
    mascot.set_state(state)
    assert mascot.state == state
    assert mascot.accessibleName().startswith('Маскот Eidos: ')
    mascot.show()
    mascot.grab()  # Every state must also be paintable.
    mascot.close()


def test_mascot_level_is_real_clipped_and_not_synthetic(app):
    mascot = Mascot()
    mascot.set_state('listening')
    for supplied, expected in [(-1, 0), (0.125, 0.125), (2, 1), (float('nan'), 0)]:
        mascot.set_level(supplied)
        assert mascot.level == expected
    mascot.show()
    mascot.set_level(0.25)
    QTest.qWait(120)
    assert mascot.level == 0.25
    mascot.close()


def test_visual_timers_stop_when_hidden_or_reduced(app):
    mascot = Mascot()
    mascot.show()
    mascot.set_state('speaking')
    assert mascot.visual_timer.isActive()
    mascot.hide()
    assert not mascot.visual_timer.isActive()
    assert mascot.animation.state() == QAbstractAnimation.State.Stopped
    assert mascot.offset == 0
    mascot.show()
    assert mascot.visual_timer.isActive()
    mascot.set_animations(False)
    assert not mascot.visual_timer.isActive()
    mascot.set_state('thinking')
    assert not mascot.visual_timer.isActive()
    mascot.close()


def test_position_clamps_to_nearest_available_monitor():
    from eidos.ui.floating import clamp_position
    screens = [QRect(-1920, 0, 1920, 1040), QRect(0, 0, 1920, 1040)]
    assert clamp_position(QPoint(-1800, 100), QSize(300, 250), screens) == QPoint(-1800, 100)
    assert clamp_position(QPoint(5000, 1200), QSize(300, 250), screens) == QPoint(1620, 790)
    assert clamp_position(QPoint(-2300, -100), QSize(300, 250), screens) == QPoint(-1920, 0)
    assert clamp_position(QPoint(30, 30), QSize(400, 300), [QRect(0, 0, 200, 100)]) == QPoint(0, 0)


def test_floating_status_controls_and_pin(app):
    from eidos.ui.floating import FloatingMascot
    widget = FloatingMascot()
    received = []
    for name in ('start', 'stop', 'pause', 'open'):
        getattr(widget, name + '_requested').connect(lambda n=name: received.append(n))
        getattr(widget, name + '_button').click()
    assert received == ['start', 'stop', 'pause', 'open']
    widget.set_status('speaking', 'Читаю ответ')
    assert widget.mascot.state == 'speaking'
    assert 'Читаю ответ' in widget.status_label.text()
    assert widget.stop_button.isEnabled()
    widget.set_status('paused', 'Микрофон отключён')
    assert widget.stop_button.isEnabled()
    assert 'Микрофон отключён' in widget.accessibleDescription()
    widget.set_level(0.4)
    assert widget.mascot.level == 0.4
    widget.set_pinned(True)
    assert widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    widget.set_pinned(False)
    assert not widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    widget.restore_position(99999, 99999)
    assert any(screen.availableGeometry().contains(widget.geometry()) for screen in app.screens())
    widget.close()


def test_drag_emits_position_only_on_release(app):
    from eidos.ui.floating import FloatingMascot
    widget = FloatingMascot()
    widget.show()
    app.processEvents()
    positions = []
    widget.position_changed.connect(lambda x, y: positions.append((x, y)))
    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=QPoint(15, 15))
    QTest.mouseMove(widget, QPoint(55, 45))
    assert positions == []
    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=QPoint(55, 45))
    assert positions == [(widget.x(), widget.y())]
    widget.close()


def test_click_does_not_persist_position(app):
    from eidos.ui.floating import FloatingMascot
    widget = FloatingMascot()
    widget.show()
    app.processEvents()
    positions = []
    widget.position_changed.connect(lambda x, y: positions.append((x, y)))
    QTest.mouseClick(widget.status_label, Qt.MouseButton.LeftButton)
    assert positions == []
    widget.hide()
    assert not widget.mascot.visual_timer.isActive()
    widget.close()
