from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtTest import QTest
from eidos.ui.pages.gestures import CameraPreview
from eidos.ui.toast import Toasts
from eidos.ui.localized import QWidget
from test_ui import app


def test_camera_preview_fills_wide_frame_without_letterbox(app):
    preview = CameraPreview()
    preview.resize(800, 260)
    image = QImage(640, 480, QImage.Format.Format_RGB32)
    image.fill(QColor('red'))
    preview.set_image(image)
    preview.show()
    try:
        rendered = preview.grab().toImage()
        assert rendered.pixelColor(10, 120).red() > 200
        assert rendered.pixelColor(790, 120).red() > 200
        assert rendered.pixelColor(400, 10).red() > 200
    finally:
        preview.close()


def test_toast_expires_without_showing_owner(app):
    owner = QWidget()
    owner.hide()
    notices = Toasts(owner)
    try:
        notices.show('Настройки сохранены.')
        assert notices.notice.isVisible() and not owner.isVisible()
        assert notices.notice.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
        notices.timer.start(20)
        QTest.qWait(40)
        assert not notices.notice.isVisible()
    finally:
        notices.close()
        owner.close()


def test_video_toolbar_and_separate_calibration_page(app, tmp_path):
    from eidos.core.config import ConfigStore
    from eidos.ui.main_window import MainWindow
    from test_ui import wait_until
    window = MainWindow(ConfigStore(tmp_path / 'config.json'))
    try:
        window.resize(1200, 800)
        window.show()
        window.navigate(2)
        page = window.gestures
        QTest.qWait(50)
        assert page.preview.height() > 400
        assert page.video_toolbar.parentWidget() is page.preview
        assert page.preview.rect().contains(page.video_toolbar.geometry())
        assert not page.emergency_button.isVisible()
        assert not page.control.isChecked()
        assert page.camera_button.text() == '' and page.camera_button.toolTip()
        page.details_button.click()
        app.processEvents()
        assert page.camera_pages.currentWidget() is page.calibration_page
        assert not page.preview.isVisible() and page.save_button.isVisible()
        assert not page.calibration_scroll.isAncestorOf(page.save_button)
        page.back_to_camera.click()
        app.processEvents()
        assert page.camera_pages.currentIndex() == 0 and page.preview.isVisible()
    finally:
        window.request_exit()
        wait_until(app, lambda: window._allow_close)
