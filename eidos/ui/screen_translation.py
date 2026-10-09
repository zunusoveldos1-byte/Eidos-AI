"""Screen selection and click-through translation layers in Qt logical coordinates."""
import threading
from functools import lru_cache

from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QKeySequence, QShortcut, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QLabel, QPushButton

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

    def __init__(self, screen, snapshot):
        super().__init__()
        self.screen = screen
        self.snapshot = snapshot
        self.start = self.end = None
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(screen.geometry())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
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
            if rect.width() >= 8 and rect.height() >= 8:
                self.selected.emit(self, rect)
            else:
                self.cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.snapshot)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 115))
        if self.start is not None:
            rect = QRectF(QPointF(self.start), QPointF(self.end)).normalized().toAlignedRect()
            painter.save()
            painter.setClipRect(rect)
            painter.drawPixmap(self.rect(), self.snapshot)
            painter.restore()
            painter.setPen(QPen(QColor('#2FE09B'), 2))
            painter.drawRect(rect)
        painter.setPen(QColor('white'))
        painter.drawText(QPoint(24, 36), 'Выделите текст мышью • Esc / правая кнопка — отмена')


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
            from eidos.modules.ocr.interface import JonSnowTranslator
            adapter = JonSnowTranslator(self.ocr, self.translator)
            lines = adapter.process(self.image, self.source, self.target, getattr(self, 'provider', 'google'),
                                    self.cancel, self.progress.emit, self.recognized.emit)
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
            if isinstance(self.translator, OnlineTranslator):
                translated = self.translator.translate(self.text, self.source, self.target,
                                                       cancel=self.cancel, progress=self.progress.emit)
            else:
                translated = self.translator.translate(self.text, self.source, self.target)
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
            if line.translation.strip() == line.text.strip():
                continue
            box = line.rect
            rect = QRectF(box.x() * sx, box.y() * sy, box.width() * sx, box.height() * sy)
            # Sample just outside the text so the cover follows the original UI color.
            x = max(0, min(self.image.width() - 1, int(box.x()) - 2))
            y = max(0, min(self.image.height() - 1, int(box.y()) - 2))
            background = self.image.pixelColor(x, y)
            background.setAlpha(255)
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
            needed_width = metrics.horizontalAdvance(line.translation)
            width = max(rect.width(), min(needed_width + 3, right - rect.left()))
            text_rect = QRectF(rect.x(), rect.y(), width, rect.height())
            if needed_width > width:
                bounds = metrics.boundingRect(QRectF(0, 0, width, 10000),
                    int(Qt.TextFlag.TextWordWrap), line.translation)
                text_rect.setHeight(max(rect.height(), min(bounds.height(), bottom - rect.top())))
            painter.fillRect(text_rect.adjusted(-2, -1, 2, 1), background)
            painter.save()
            painter.setClipRect(text_rect.adjusted(-1, -1, 1, 1))
            if needed_width > width:
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft |
                                 Qt.TextFlag.TextWordWrap, line.translation)
            else:
                ink_top = metrics.tightBoundingRect(line.text).top()
                painter.drawText(QPointF(text_rect.x(), text_rect.y() - ink_top), line.translation)
            painter.restore()


class OverlayControls(QWidget):
    dismissed = pyqtSignal()
    return_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, screen, region=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet('background: #15241C; color: white; padding: 6px;')
        layout = QHBoxLayout(self)
        self.status_label = QLabel('Перевод выбранной области')
        self.status_label.setMinimumWidth(230)
        layout.addWidget(self.status_label)
        refresh = QPushButton('Обновить область')
        refresh.clicked.connect(self.refresh_requested)
        layout.addWidget(refresh)
        back = QPushButton('Показать результат')
        close = QPushButton('Убрать перевод (Esc)')
        back.clicked.connect(self.return_requested)
        close.clicked.connect(self.dismissed)
        layout.addWidget(back)
        layout.addWidget(close)
        shortcut = QShortcut(QKeySequence('Esc'), self)
        shortcut.activated.connect(self.dismissed)
        self.adjustSize()
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 16, area.top() + 16)
        if region is not None and self.geometry().intersects(region):
            self.move(area.right() - self.width() - 16, area.bottom() - self.height() - 16)
