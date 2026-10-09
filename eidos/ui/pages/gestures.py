from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..components import Card, Page, ResponsiveRow, button, combo, label
from ..icons import icon
from ..mascot import Mascot


class GesturesPage(Page):
    def __init__(self) -> None:
        super().__init__('Управление жестами', 'Управляйте компьютером движениями руки')
        self.badge()
        camera_card = Card(margins=20)
        camera_card.heading('Камера')
        camera = Card(margins=20)
        camera.setObjectName('camera')
        camera.setMinimumHeight(245)
        camera.body.addStretch()
        image = QLabel()
        image.setPixmap(icon('camera', '#82958A', 50).pixmap(50, 50))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        camera.body.addWidget(image)
        camera.body.addWidget(label('Камера выключена', 'secondary', True))
        camera.body.addStretch()
        camera_card.body.addWidget(camera, 1)
        self.camera = combo()
        self.camera.addItem('Выберите камеру')
        self.camera.setEnabled(False)
        self.camera.setToolTip('Выбор камеры появится после подключения модуля жестов')
        camera_card.body.addWidget(self.camera)
        self.camera_button = button('Включить камеру', 'camera')
        self.camera_button.setEnabled(False)
        camera_card.body.addWidget(self.camera_button)
        camera_card.body.addWidget(label('Будет доступно после подключения модуля', 'muted', True))
        gestures = Card(margins=20)
        gestures.heading('Доступные жесты')
        for name, title, detail in [
            ('pinch', 'Сведение пальцев', 'Управление громкостью'),
            ('hand', 'Открытая ладонь', 'Пауза / воспроизведение'),
            ('finger', 'Указательный палец', 'Управление курсором на экране'),
        ]:
            card = Card(margins=14)
            row = QHBoxLayout()
            drawing = QLabel()
            drawing.setPixmap(icon(name, '#D8E3DC', 62).pixmap(62, 62))
            drawing.setFixedWidth(70)
            row.addWidget(drawing)
            texts = QVBoxLayout()
            texts.addWidget(label(title, 'h3'))
            texts.addWidget(label(detail, 'secondary'))
            row.addLayout(texts, 1)
            row.addWidget(label('Планируется', 'soon'))
            card.body.addLayout(row)
            card.setMinimumHeight(98)
            gestures.body.addWidget(card)
        gestures.body.addStretch()
        self.body.addWidget(ResponsiveRow([camera_card, gestures], threshold=700))
        help_card = Card(margins=22)
        content = QWidget()
        copy = QVBoxLayout(content)
        copy.setContentsMargins(0, 0, 0, 0)
        copy.addWidget(label('Как пользоваться', 'h2'))
        copy.addWidget(label('После подключения модуля включите камеру и держите руку в кадре. '
                             'Выполняйте жесты в хорошо освещённом месте, чтобы система могла их распознать.', 'secondary'))
        self.mascot = Mascot(125)
        row = QHBoxLayout()
        row.addWidget(content, 1)
        row.addWidget(self.mascot)
        help_card.body.addLayout(row)
        self.body.addWidget(help_card)
        self.body.addStretch()
