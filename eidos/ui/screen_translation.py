"""Screen selection and click-through translation layers in Qt logical coordinates."""
import threading
import math
import time
from functools import lru_cache

from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QKeySequence, QShortcut, QPixmap, QRegion
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QGraphicsDropShadowEffect
from eidos.ui.localized import QWidget, QLabel, QPushButton

from eidos.modules.ocr.engine import WindowsOCR, OnlineTranslator
from eidos.modules.ocr.multilingual import ScreenOCR


@lru_cache(maxsize=2048)
def source_font(text, height):
    """Estimate source pixel size from its ink height; translation length never changes it."""
    font = QFont(QApplication.font())
    best_size, best_error = 8, float('inf')
    lower, upper = 6, max(9, int(height * 2.5))
    while lower <= upper:
        middle = (lower + upper) // 2
        font.setPixelSize(middle)
        if QFontMetricsF(font).tightBoundingRect(text).height() < height:
            lower = middle + 1
        else:
            upper = middle - 1
    for size in range(max(6, lower - 3), lower + 4):
        font.setPixelSize(size)
        ink = QFontMetricsF(font).tightBoundingRect(text).height()
        error = abs(ink - height)
        if error < best_error:
            best_size, best_error = size, error
    font.setPixelSize(best_size)
    return font


class RegionSelector(QWidget):
    selected = pyqtSignal(object, object)
    cancelled = pyqtSignal()
    entered = pyqtSignal(object)

    def __init__(self, screen, snapshot):
        super().__init__()
        self.screen = screen
        self.snapshot = snapshot
        self.start = self.end = None
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(screen.geometry())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.glow_enabled = True
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(50)
        self.pulse_timer.timeout.connect(self._pulse)
        self._pulse_started = time.monotonic()
        self.pulse_timer.start()
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            self.cancelled.emit()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.start = self.end = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.start is not None:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.start is not None:
            self.end = event.position().toPoint()
            rect = QRectF(QPointF(self.start), QPointF(self.end)).normalized().toAlignedRect().intersected(self.rect())
            self.close()
            if rect.width() >= 8 and rect.height() >= 8:
                self.pulse_timer.stop()
                self.selected.emit(self, rect)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()

    def enterEvent(self, event):
        self.entered.emit(self)
        super().enterEvent(event)

    def _pulse(self):
        border = QRegion(self.rect()).subtracted(QRegion(self.rect().adjusted(36, 36, -36, -36)))
        self.update(border)

    def closeEvent(self, event):
        self.pulse_timer.stop()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 32))
        if self.start is not None:
            rect = QRectF(QPointF(self.start), QPointF(self.end)).normalized().toAlignedRect()
            painter.save()
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            painter.restore()
            painter.setPen(QPen(QColor('#2FE09B'), 2))
            painter.drawRect(rect)
        if self.glow_enabled:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pulse = .7 + .3 * math.sin((time.monotonic() - self._pulse_started) * 3)
            for width in range(32, 2, -3):
                color = QColor('#25E6A1')
                color.setAlpha(round((36 - width) * .55 * pulse))
                painter.setPen(QPen(color, width))
                painter.drawRect(self.rect().adjusted(2, 2, -3, -3))
            color = QColor('#25E6A1')
            color.setAlpha(round(255 * pulse))
            painter.setPen(QPen(color, 3))
            painter.drawRect(self.rect().adjusted(2, 2, -3, -3))
        painter.setPen(QColor('white'))
        from eidos.core.i18n import tr
        painter.drawText(QPoint(24, 36), tr('Выделите текст мышью • Esc / правая кнопка — отмена'))


class TranslationWorker(QThread):
    recognized = pyqtSignal(str)
    result = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, image, source, target, parent=None, ocr=None, translator=None):
        super().__init__(parent)
        self.image, self.source, self.target = image, source, target
        self.ocr = ocr or ScreenOCR()
        self.translator = translator or OnlineTranslator()
        self.cancel = threading.Event()
        if isinstance(self.ocr, ScreenOCR):
            self.ocr.progress = self.progress.emit

    def run(self):
        try:
            self.progress.emit('Распознавание текста…')
            from eidos.agent.harness import TaskContext
            from eidos.agent.screen import screen_registry
            context = TaskContext(cancel=self.cancel, screen_image=self.image,
                                  secret_values=getattr(self, 'secret_values', ()),
                                  progress=lambda state, text: self.progress.emit(text))
            registry = screen_registry(self.ocr, self.translator, self.recognized.emit)
            lines = registry.execute('screen_translate', {'source': self.source, 'target': self.target,
                                     'provider': getattr(self, 'provider', 'google')}, context).data
            if not self.cancel.is_set():
                self.result.emit(lines)
        except Exception as exc:
            if not self.cancel.is_set():
                detail = str(exc) or 'Превышено время ожидания распознавания. Попробуйте снова.'
                self.failed.emit(f'Не удалось перевести: {detail}')


class TextTranslationWorker(QThread):
    result = pyqtSignal(str)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, text, source, target, parent=None, translator=None):
        super().__init__(parent)
        self.text, self.source, self.target = text, source, target
        self.translator = translator or OnlineTranslator()
        self.cancel = threading.Event()

    def run(self):
        try:
            self.progress.emit('Перевод исправленного текста…')
            from eidos.agent.harness import TaskContext
            from eidos.agent.screen import screen_registry
            context = TaskContext(cancel=self.cancel, secret_values=getattr(self, 'secret_values', ()),
                                  progress=lambda state, text: self.progress.emit(text))
            translated = screen_registry(translator=self.translator).execute('text_translate',
                {'text': self.text, 'source': self.source, 'target': self.target, 'provider': 'google'}, context).text
            if not self.cancel.is_set():
                self.result.emit(translated)
        except Exception as exc:
            if not self.cancel.is_set():
                self.failed.emit(f'Не удалось перевести текст: {exc}')


class TranslationOverlay(QWidget):
    def __init__(self, geometry, image, lines):
        super().__init__()
        self.image, self.lines = image, lines
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                            Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(geometry)
        self._content_signature = self.content_signature(image, lines)
        self._raster = None

    @staticmethod
    def content_signature(image, lines):
        if image.isNull():
            return ()
        return (image.width(), image.height(), tuple(
            (line.text, line.translation, line.rect.getRect(), image.pixelColor(
                max(0, min(image.width() - 1, int(line.rect.x()) - 2)),
                max(0, min(image.height() - 1, int(line.rect.y()) - 2))).rgba())
            for line in lines))

    def set_content(self, image, lines):
        signature = self.content_signature(image, lines)
        self.image, self.lines = image, lines
        if signature == self._content_signature:
            return False
        self._content_signature = signature
        self._raster = None
        self.update()
        return True

    def paintEvent(self, event):
        ratio = self.devicePixelRatioF()
        size = (round(self.width() * ratio), round(self.height() * ratio))
        if (self._raster is None or (self._raster.width(), self._raster.height()) != size
                or self._raster.devicePixelRatioF() != ratio):
            self._raster = QPixmap(*size)
            self._raster.setDevicePixelRatio(ratio)
            self._raster.fill(Qt.GlobalColor.transparent)
            rendered = QPainter(self._raster)
            self._draw_content(rendered)
            rendered.end()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._raster)

    def _draw_content(self, painter):
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self.image.isNull():
            return
        sx, sy = self.width() / self.image.width(), self.height() / self.image.height()
        rectangles = [(line.rect.x() * sx, line.rect.y() * sy,
                       line.rect.right() * sx, line.rect.bottom() * sy) for line in self.lines]
        for index, line in enumerate(self.lines):
            display = line.translation or line.text
            box = line.rect
            rect = QRectF(box.x() * sx, box.y() * sy, box.width() * sx, box.height() * sy)
            # Sample just outside the text so the cover follows the original UI color.
            x = max(0, min(self.image.width() - 1, int(box.x()) - 2))
            y = max(0, min(self.image.height() - 1, int(box.y()) - 2))
            background = self.image.pixelColor(x, y)
            background.setAlpha(225)
            luminance = .2126 * background.red() + .7152 * background.green() + .0722 * background.blue()
            painter.setPen(QColor('#111111' if luminance > 140 else '#FFFFFF'))
            font = source_font(line.text, rect.height())
            painter.setFont(font)
            metrics = QFontMetricsF(font)
            # Use adjacent free space for a longer translation, preserving font size.
            right = self.width() - 2
            bottom = self.height() - 2
            left_edge, top_edge, right_edge, bottom_edge = rectangles[index]
            for other_index, (other_left, other_top, other_right, other_bottom) in enumerate(rectangles):
                if other_index == index:
                    continue
                if other_top < bottom_edge and other_bottom > top_edge and other_left > right_edge:
                    right = min(right, other_left - 3)
                if other_top > bottom_edge and other_left < right and other_right > left_edge:
                    bottom = min(bottom, other_top - 2)
            needed_width = metrics.horizontalAdvance(display)
            width = max(rect.width(), min(needed_width + 3, right - rect.left()))
            text_rect = QRectF(rect.x(), rect.y(), width, rect.height())
            if needed_width > width:
                bounds = metrics.boundingRect(QRectF(0, 0, width, 10000),
                    int(Qt.TextFlag.TextWordWrap), display)
                text_rect.setHeight(max(rect.height(), min(bounds.height(), bottom - rect.top())))
            painter.fillRect(text_rect.adjusted(-2, -1, 2, 1), background)
            painter.save()
            painter.setClipRect(text_rect.adjusted(-1, -1, 1, 1))
            if needed_width > width:
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft |
                                 Qt.TextFlag.TextWordWrap, display)
            else:
                ink_top = metrics.tightBoundingRect(line.text).top()
                painter.drawText(QPointF(text_rect.x(), text_rect.y() - ink_top), display)
            painter.restore()


class OverlayControls(QWidget):
    dismissed = pyqtSignal()
    return_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, screen, region=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet('''
            QWidget#translationPanel { background: #0B110F; border: 1px solid #1E2923;
                border-radius: 10px; }
            QLabel { background: transparent; color: #E2E8F0; border: none; }
            QPushButton { background: #0F1714; color: #E2E8F0; border: 1px solid #1E2923;
                border-radius: 7px; padding: 8px 12px; }
            QPushButton:hover, QPushButton:focus { border-color: #10B981; color: #25E6A1; }
            QPushButton:pressed { background: #16372A; }
        ''')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 22)
        self.panel = QWidget(self)
        self.panel.setObjectName('translationPanel')
        self.panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout.addWidget(self.panel)
        layout = QHBoxLayout(self.panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        shadow = QGraphicsDropShadowEffect(self.panel)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.panel.setGraphicsEffect(shadow)
        self.status_label = QLabel('Перевод выбранной области')
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumWidth(200)
        self.status_label.setMaximumWidth(420)
        layout.addWidget(self.status_label)
        refresh = QPushButton('Обновить область')
        refresh.clicked.connect(self.refresh_requested)
        layout.addWidget(refresh)
        back = QPushButton('Показать результат')
        close = QPushButton('Убрать перевод (Esc)')
        back.clicked.connect(self.return_requested)
        close.clicked.connect(self.dismissed)
        back.setParent(self)
        back.hide()
        layout.addWidget(close)
        self.escape_shortcut = QShortcut(QKeySequence('Esc'), self)
        self.escape_shortcut.activated.connect(self.dismissed)
        self.dismissed.connect(self.close)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.adjustSize()
        self.reposition(screen, region)

    def showEvent(self, event):
        super().showEvent(event)
        # The result layer is click-through; this small panel owns keyboard input.
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismissed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def reposition(self, screen, region=None):
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 16, area.top() + 16)
        if region is not None and self.geometry().intersects(region):
            self.move(area.right() - self.width() - 16, area.bottom() - self.height() - 16)
