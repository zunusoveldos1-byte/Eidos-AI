"""Render a preview of the six actual mascot widget states."""
import os
from pathlib import Path
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QGridLayout, QLabel, QVBoxLayout, QWidget
from eidos.ui.mascot import Mascot
from eidos.ui.theme import install_font


def main():
    app = QApplication([])
    install_font()
    panel = QWidget()
    panel.setStyleSheet('background: #111a16; color: #d8eee2; font: 14px "Inter";')
    grid = QGridLayout(panel)
    for index, (state, title) in enumerate((
        ('ready', 'Ожидание и моргание'), ('listening', 'Внимательно слушает'),
        ('thinking', 'Думает'), ('speaking', 'Говорит'),
        ('success', 'Задача выполнена'), ('error', 'Не понял / ошибка'),
    )):
        card = QVBoxLayout()
        mascot = Mascot(200)
        mascot.set_animations(False)
        mascot.set_state(state)
        card.addWidget(mascot, alignment=Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.addWidget(title_label)
        grid.addLayout(card, index // 3, index % 3)
    panel.resize(720, 490)
    panel.show()
    app.processEvents()
    output = Path('docs/screenshots/mascot-emotions.png')
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.grab().save(str(output))
    panel.close()
    print(output.resolve())


if __name__ == '__main__':
    main()
