"""Shared design tokens and Qt stylesheet for all five pages."""
from pathlib import Path
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QApplication

BACKGROUND = '#0D1110'
SURFACE = '#151B18'
BORDER = '#29362F'
ACCENT = '#2FE09B'
TEXT = '#F2F6F3'
SECONDARY = '#A8B7AE'
ASSETS = Path(__file__).resolve().parents[1] / 'assets'
_font_loaded = False

def install_font() -> None:
    global _font_loaded
    if not _font_loaded:
        QFontDatabase.addApplicationFont(str(ASSETS / 'fonts' / 'Inter.ttf'))
        _font_loaded = True
    font = QFont('Inter' if 'Inter' in QFontDatabase.families() else 'Segoe UI', 10)
    QApplication.instance().setFont(font)

STYLE = '''
QWidget { color: #F2F6F3; font-family: "Inter", "Segoe UI"; font-size: 14px; }
QMainWindow, QWidget#shell, QWidget#page, QWidget#pageContent { background: #0D1110; }
QWidget#sidebar { background: #101613; border-right: 1px solid #29362F; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 29px; font-weight: 700; }
QLabel#h1 { font-size: 30px; font-weight: 700; }
QLabel#heroTitle { font-size: 32px; font-weight: 700; }
QLabel#h2 { font-size: 21px; font-weight: 600; }
QLabel#h3 { font-size: 17px; font-weight: 600; }
QLabel#subtitle { font-size: 17px; color: #A8B7AE; }
QLabel#secondary { color: #A8B7AE; }
QLabel#muted { font-size: 12px; color: #82958A; }
QLabel#moduleBadge { color: #E4BC76; background: #282419; border: 1px solid #776138; border-radius: 13px; padding: 7px 11px; font-size: 12px; }
QLabel#soon { color: #A8B7AE; background: #232C29; border: 1px solid #33443B; border-radius: 11px; padding: 4px 11px; font-size: 11px; }
QFrame#card { background: #151B18; border: 1px solid #29362F; border-radius: 13px; }
QFrame#hero { background: qlineargradient(x1:0,y1:1,x2:1,y2:0,stop:0 #14251D,stop:0.65 #182E24,stop:1 #27493A); border: 1px solid #365245; border-radius: 16px; }
QFrame#camera { background: #222B29; border: 1px solid #34413A; border-radius: 10px; }
QFrame#line { background: #29362F; border: none; max-height: 1px; }
QPushButton { background: #202925; border: 1px solid #35453C; border-radius: 9px; padding: 10px 16px; min-height: 20px; }
QPushButton:hover { background: #2B3932; border-color: #4B6958; }
QPushButton:pressed { background: #18251E; }
QPushButton:disabled { background: #1C2520; color: #72847A; border-color: #2B3931; }
QPushButton:focus, QComboBox:focus, QPlainTextEdit:focus { border: 2px solid #2FE09B; }
QPushButton#primary { background: #2FE09B; color: #061B12; border: 1px solid #2FE09B; font-weight: 600; }
QPushButton#primary:hover { background: #54EAAF; border-color: #54EAAF; }
QPushButton#primary:pressed { background: #20C788; }
QPushButton#primary:disabled { background: #1C4031; color: #628B77; border-color: #284B3B; }
QPushButton#nav { text-align: left; background: transparent; border: 1px solid transparent; padding: 12px 16px; font-size: 15px; }
QPushButton#nav:hover { background: #1B2821; }
QPushButton#nav:checked { background: #1B3428; border-left: 3px solid #2FE09B; color: #2FE09B; font-weight: 600; }
QPushButton#nav:focus { border: 1px solid #2FE09B; }
QPushButton#iconButton { background: transparent; border: 1px solid transparent; padding: 4px; min-width: 22px; min-height: 22px; }
QPushButton#iconButton:hover { background: #25352B; border-color: #344E3E; }
QPushButton#iconButton:focus { border-color: #2FE09B; }
QPushButton#chip { background: #1B3428; border: none; border-radius: 17px; padding: 7px 18px; font-size: 12px; }
QPushButton#chip:hover { background: #284D3B; }
QPushButton#details { text-align: left; background: transparent; border: none; padding: 5px; color: #A8B7AE; }
QComboBox { background: #151E18; border: 1px solid #35453C; border-radius: 8px; padding: 10px 30px 10px 12px; min-height: 20px; }
QComboBox:hover { border-color: #577A64; }
QComboBox:disabled { color: #788B80; background: #171F1A; border-color: #29362F; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: url(__CHEVRON__); width: 16px; height: 16px; }
QComboBox QAbstractItemView { background: #1B2720; border: 1px solid #405548; color: #F2F6F3; selection-background-color: #285B40; padding: 4px; }
QPlainTextEdit { background: #19211C; border: 1px solid #29362F; border-radius: 10px; padding: 14px; selection-background-color: #286A49; font-size: 18px; }
QPlainTextEdit#journal { background: #111813; font-size: 12px; padding: 8px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #101713; width: 8px; margin: 3px 0; }
QScrollBar::handle:vertical { background: #3C5143; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: #22372B; color: #F2F6F3; border: 1px solid #456753; padding: 6px; }
QMessageBox { background: #151B18; }
QLineEdit, QSpinBox, QDateTimeEdit { background: #19211C; color: #F2F6F3; border: 1px solid #35453C; border-radius: 8px; padding: 9px; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: #2FE09B; }
QListWidget { background: #151E18; border: 1px solid #35453C; border-radius: 8px; padding: 8px; }
QListWidget::item { padding: 8px; }
QListWidget::item:selected { background: #1B3428; color: #2FE09B; }
QTabWidget::pane { border: 1px solid #29362F; border-radius: 10px; }
QTabBar::tab { background: #151E18; color: #A8B7AE; padding: 11px 14px; }
QTabBar::tab:selected { background: #1B3428; color: #2FE09B; border-bottom: 2px solid #2FE09B; }
QCheckBox { spacing: 9px; }
QDialog { background: #101713; }
QPlainTextEdit#conversation { font-size: 14px; padding: 12px; }
'''.replace('__CHEVRON__', (ASSETS / 'icons' / 'chevron.svg').as_posix())
