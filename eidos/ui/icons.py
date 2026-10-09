"""Small consistent SVG icons; no network or third-party dependency."""
from functools import lru_cache
from PyQt6.QtCore import QByteArray, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from .theme import ASSETS, SECONDARY

@lru_cache(maxsize=128)
def icon(name: str, color: str = SECONDARY, size: int = 24) -> QIcon:
    source = (ASSETS / 'icons' / f'{name}.svg').read_text(encoding='utf-8')
    renderer = QSvgRenderer(QByteArray(source.replace('currentColor', color).encode()))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)
