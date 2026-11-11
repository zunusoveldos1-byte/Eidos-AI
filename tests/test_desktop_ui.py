from threading import Event
from types import SimpleNamespace
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtTest import QTest
from eidos.ui.desktop_commands import DesktopUI, Request
from eidos.ui.localized import QWidget
from test_ui import app, wait_until


def test_region_success_is_delayed_until_clipboard_contains_new_image(app, monkeypatch):
    window = QWidget()
    window._closing = False
    ui = DesktopUI(window)
    launches = []
    monkeypatch.setattr('eidos.ui.desktop_commands.os.startfile', launches.append)
    request = Request('screenshot', {'mode': 'region'}, Event())
    try:
        app.clipboard().clear()
        ui.execute(request)
        assert launches == ['ms-screenclip:'] and not request.done.is_set()
        image = QImage(40, 30, QImage.Format.Format_RGB32)
        image.fill(QColor('green'))
        app.clipboard().setImage(image)
        wait_until(app, request.done.is_set)
        assert request.done.is_set() and request.answer == 'Скриншот в буфере обмена'
        assert not request.error
    finally:
        request.cancel.set()
        window.close()


def test_cancel_region_never_reports_copy_success(app, monkeypatch):
    window = QWidget()
    window._closing = False
    ui = DesktopUI(window)
    monkeypatch.setattr('eidos.ui.desktop_commands.os.startfile', lambda value: None)
    request = Request('screenshot', {'mode': 'region'}, Event())
    try:
        ui.execute(request)
        request.cancel.set()
        wait_until(app, request.done.is_set)
        assert request.done.is_set() and request.answer == '' and request.error
    finally:
        window.close()
