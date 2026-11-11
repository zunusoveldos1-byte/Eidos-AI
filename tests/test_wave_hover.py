from PyQt6.QtCore import QEvent, QPointF
from PyQt6.QtGui import QEnterEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from test_ui import app, wait_until
from test_home_refresh import window


def test_tools_hover_preserves_background_and_selection(window, app):
    nav = window.sidebar.group.button(6)
    assert nav.toolTip() == 'Инструменты'
    before = nav.grab().toImage().pixelColor(nav.width() - 10, nav.height() // 2)
    QApplication.sendEvent(nav, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
    nav.animation.setCurrentTime(70)
    assert 0 < nav.hover < 1
    wait_until(app, lambda: nav.animation.state().name == 'Stopped')
    assert nav.hover == 1
    after = nav.grab().toImage().pixelColor(nav.width() - 10, nav.height() // 2)
    assert before == after
    assert window.sidebar.group.button(0).isChecked()
    nav.click()
    assert nav.isChecked() and window.pages.currentIndex() == 6
    nav.setFocus()
    app.processEvents()
    assert nav.hasFocus()
    focused = nav.grab().toImage()
    nav.clearFocus()
    app.processEvents()
    assert focused != nav.grab().toImage()
    QApplication.sendEvent(nav, QEvent(QEvent.Type.Leave))
    QTest.qWait(200)
    wait_until(app, lambda: nav.animation.state().name == 'Stopped')
    assert nav.hover == 0 and nav.isChecked()


def test_static_glow_and_paint_resources_are_reused(window, app):
    from dataclasses import replace
    window.config = replace(window.config, reduce_animations=True)
    window._apply_preferences()
    assert not window.home.motion_timer.isActive()
    renderer = window.home.content.waves
    assert len(renderer.highlights) == 6
    original = tuple(id(p) for p in renderer.paths + [renderer.ribbon])
    first = window.home.content.grab().toImage()
    QTest.qWait(100)
    second = window.home.content.grab().toImage()
    assert first == second
    assert original == tuple(id(p) for p in renderer.paths + [renderer.ribbon])
    assert any(first.pixelColor(x, y).green() > 60
               for y in range(first.height() - 165, first.height() - 30, 3)
               for x in range(70, first.width() - 70, 3))


def test_glow_cycle_boundary_is_dark_and_speeds_are_independent():
    from eidos.ui.waves import WaveRenderer
    renderer = WaveRenderer()
    assert len({h.duration for h in renderer.highlights}) == 6
    for light in renderer.highlights:
        boundary = light.duration - light.delay
        light.update(boundary - .001)
        assert light.opacity < .000001
        light.update(boundary + .001)
        assert light.opacity < .000001
        assert len(light.points) == 25
