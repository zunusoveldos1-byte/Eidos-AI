"""Reusable native widgets, responsive rows and scrollable pages."""
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractButton, QApplication, QBoxLayout, QComboBox, QFrame, QHBoxLayout,
    QLabel, QLayout, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QStyle,
    QStyleOptionComboBox, QStylePainter, QVBoxLayout, QWidget,
)
from .icons import icon
from .theme import ACCENT

def label(text: str, role: str = '', centered: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if role in {'soon', 'moduleBadge'}:
        widget.setWordWrap(False)
        widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    if centered:
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget

def button(text: str, name: str | None = None, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setObjectName('primary')
    if name:
        widget.setIcon(icon(name, '#061B12' if primary else '#A8B7AE'))
        widget.setIconSize(QSize(21, 21))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget

def icon_button(name: str, tooltip: str) -> QPushButton:
    widget = button('', name)
    widget.setObjectName('iconButton')
    widget.setToolTip(tooltip)
    widget.setAccessibleName(tooltip)
    widget.setFixedSize(34, 34)
    return widget

class ElidingComboBox(QComboBox):
    """Long device names use an ellipsis and retain their full tooltip."""
    def __init__(self) -> None:
        super().__init__()
        self.currentIndexChanged.connect(lambda: self.setToolTip(self.currentText()))

    def paintEvent(self, event) -> None:
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        field = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                           QStyle.SubControl.SC_ComboBoxEditField, self)
        option.currentText = self.fontMetrics().elidedText(option.currentText, Qt.TextElideMode.ElideRight, max(field.width() - 6, 0))
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        painter.drawControl(QStyle.ControlElement.CE_ComboBoxLabel, option)


def combo() -> QComboBox:
    widget = ElidingComboBox()
    widget.setMinimumWidth(0)
    widget.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    widget.setMinimumContentsLength(12)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget

class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, margins: int = 22) -> None:
        super().__init__(parent)
        self.setObjectName('card')
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(margins, margins, margins, margins)
        self.body.setSpacing(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def heading(self, text: str, name: str | None = None) -> None:
        row = QHBoxLayout()
        if name:
            image = QLabel()
            image.setPixmap(icon(name, '#F2F6F3').pixmap(25, 25))
            image.setFixedSize(28, 28)
            row.addWidget(image)
        row.addWidget(label(text, 'h2'), 1)
        self.body.addLayout(row)

class ResponsiveRow(QWidget):
    """Reflow columns below threshold rather than clipping controls."""
    def __init__(self, widgets: list[QWidget], threshold: int = 700, spacing: int = 16) -> None:
        super().__init__()
        self.threshold = threshold
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(spacing)
        self.row.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        for widget in widgets:
            self.row.addWidget(widget, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def resizeEvent(self, event) -> None:
        direction = QBoxLayout.Direction.TopToBottom if self.width() < self.threshold else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
            self.updateGeometry()
        super().resizeEvent(event)

class Page(QWidget):
    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        self.setObjectName('page')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName('pageContent')
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(28, 26, 28, 22)
        self.body.setSpacing(16)
        self.body.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.header = QHBoxLayout()
        self.header.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        titles.addWidget(label(title, 'h1'))
        titles.addWidget(label(subtitle, 'subtitle'))
        self.header.addLayout(titles, 1)
        self.body.addLayout(self.header)
        self.scroll.setWidget(self.content)
        outer.addWidget(self.scroll)

    def badge(self) -> None:
        badge = label('●  Модуль пока не подключён', 'moduleBadge')
        badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.header.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

class Toggle(QAbstractButton):
    def __init__(self, accessible_name: str) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(46, 28)
        self.setAccessibleName(accessible_name)
        self.setToolTip(accessible_name)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = ACCENT if self.isChecked() else '#36413B'
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color if self.isEnabled() else '#25312A'))
        painter.drawRoundedRect(1, 3, 44, 22, 11, 11)
        painter.setBrush(QColor('#F2F6F3' if self.isEnabled() else '#77887D'))
        painter.drawEllipse(25 if self.isChecked() else 4, 5, 18, 18)
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(0, 1, 45, 26, 12, 12)

class ResultText(QPlainTextEdit):
    def __init__(self, centered: bool = False) -> None:
        super().__init__()
        self.centered = centered
        self._empty_text = ''

    def setPlaceholderText(self, text: str) -> None:
        if self.centered:
            self._empty_text = text
            self.viewport().update()
        else:
            super().setPlaceholderText(text)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.centered and not self.toPlainText():
            painter = QPainter(self.viewport())
            painter.setPen(QColor('#A8B7AE'))
            font = painter.font()
            font.setPixelSize(16)
            painter.setFont(font)
            painter.drawText(self.viewport().rect().adjusted(12, 12, -12, -12),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._empty_text)


class TextCard(Card):
    def __init__(self, title: str, placeholder: str, name: str | None = None, centered: bool = False) -> None:
        super().__init__(margins=20)
        row = QHBoxLayout()
        if name:
            image = QLabel()
            if name == 'eidos':
                from .mascot import frames
                image.setPixmap(frames()['ready'].scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                image.setPixmap(icon(name).pixmap(25, 25))
            row.addWidget(image)
        row.addWidget(label(title, 'h3'), 1)
        self.copy_button = icon_button('copy', f'Копировать: {title}')
        self.copy_button.setEnabled(False)
        row.addWidget(self.copy_button)
        self.body.addLayout(row)
        self.text = ResultText(centered)
        self.text.setReadOnly(True)
        self.text.setPlaceholderText(placeholder)
        self.text.setAccessibleName(title)
        self.text.setMinimumHeight(112 if not centered else 230)
        self.text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if centered:
            self.text.setStyleSheet('background: transparent; border: none;')
        self.body.addWidget(self.text, 1)
        self.copy_button.clicked.connect(self.copy)
        self.text.textChanged.connect(lambda: self.copy_button.setEnabled(bool(self.text.toPlainText())))

    def copy(self) -> None:
        QApplication.clipboard().setText(self.text.toPlainText())

def setting_row(text: str, control: QWidget) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 3, 0, 3)
    layout.setSpacing(14)
    layout.addWidget(label(text), 1)
    layout.addWidget(control, 1 if isinstance(control, QComboBox) else 0)
    return row
