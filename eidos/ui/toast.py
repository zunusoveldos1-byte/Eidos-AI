"""Transient, non-activating notices; never occupy the page header."""
from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication
from eidos.ui.localized import QLabel


class Toasts(QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.notice = QLabel(owner, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                             Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.notice.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.notice.setWordWrap(True)
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.setMaximumWidth(420)
        self.notice.setStyleSheet('background: #0F1714; color: #F2FAF6; border: 1px solid #25E6A1; '
                                 'border-radius: 10px; padding: 12px; font-size: 13px;')
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.notice.hide)

    def show(self, text):
        if not text or getattr(self.owner, '_closing', False): return
        self.notice.setText(text[:1000])
        self.notice.adjustSize()
        screen = self.owner.screen() if self.owner.isVisible() else QApplication.screenAt(QCursor.pos())
        area = (screen or QApplication.primaryScreen()).availableGeometry()
        self.notice.move(area.right() - self.notice.width() - 16, area.top() + 16)
        self.notice.show()
        self.timer.start(4500)

    def close(self):
        self.timer.stop()
        self.notice.hide()
