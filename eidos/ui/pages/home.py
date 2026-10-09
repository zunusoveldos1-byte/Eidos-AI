from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from ..components import Card, Page, ResponsiveRow, button, label
from ..icons import icon
from ..mascot import Mascot
from ..theme import ACCENT


class HomePage(Page):
    navigate_requested = pyqtSignal(int)
    compact_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__('Главная', 'Ваш помощник для повседневных задач')
        hero = Card(margins=28)
        hero.setObjectName('hero')
        hero.setMinimumHeight(205)
        content = QWidget()
        copy = QVBoxLayout(content)
        copy.setContentsMargins(0, 0, 0, 0)
        title = label('Добро пожаловать в Eidos', 'heroTitle')
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setText('Добро пожаловать в <span style="color: #2FE09B">Eidos</span>')
        copy.addWidget(title)
        copy.addWidget(label('Голос, жесты и перевод — в одном приложении', 'subtitle'))
        copy.addSpacing(10)
        self.voice_button = button('Открыть голосовой помощник', 'mic', True)
        self.voice_button.clicked.connect(lambda: self.navigate_requested.emit(1))
        self.compact_button = button('Компактный режим', 'monitor')
        self.compact_button.clicked.connect(self.compact_requested)
        copy.addWidget(ResponsiveRow([self.voice_button, self.compact_button], threshold=480, spacing=12))
        self.mascot = Mascot(195)
        row = QHBoxLayout()
        row.addWidget(content, 3)
        row.addWidget(self.mascot, 1)
        hero.body.addLayout(row)
        self.body.addWidget(hero)
        cards = []
        for index, (name, image, text) in enumerate([
            ('Голос', 'mic', 'Записывайте команды и получайте ответы голосом.'),
            ('Жесты', 'hand', 'Управление приложением с помощью жестов.'),
            ('Перевод', 'languages', 'Распознавание и перевод текста с экрана.'),
        ], 1):
            card = Card()
            head = QHBoxLayout()
            picture = label('')
            picture.setPixmap(icon(image, ACCENT if index == 1 else '#A8B7AE', 38).pixmap(38, 38))
            head.addWidget(picture)
            head.addWidget(label(name, 'h2'), 1)
            if index == 2:
                head.addWidget(label('Скоро', 'soon'))
            card.body.addLayout(head)
            card.body.addWidget(label(text, 'secondary'))
            card.body.addStretch()
            open_button = button('Открыть', primary=index == 1)
            open_button.clicked.connect(lambda checked=False, page=index: self.navigate_requested.emit(page))
            card.body.addWidget(open_button)
            card.setMinimumHeight(205)
            cards.append(card)
        self.body.addWidget(ResponsiveRow(cards, threshold=650))
        quick = Card(margins=20)
        quick.heading('Быстрый старт')
        steps = []
        for number, title, text in [
            (1, 'Выберите микрофон', 'Настройте устройство в настройках.'),
            (2, 'Начните запись', 'Нажмите кнопку и произнесите команду.'),
            (3, 'Получите ответ', 'Eidos распознает команду и ответит.'),
        ]:
            widget = QWidget()
            line = QHBoxLayout(widget)
            line.setContentsMargins(0, 0, 0, 0)
            badge = label(str(number), 'h2', True)
            badge.setFixedSize(38, 38)
            badge.setStyleSheet('color: #2FE09B; background: #1E3328; border-radius: 19px;')
            line.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            texts = QVBoxLayout()
            texts.addWidget(label(title))
            texts.addWidget(label(text, 'muted'))
            line.addLayout(texts, 1)
            steps.append(widget)
        quick.body.addWidget(ResponsiveRow(steps, threshold=610))
        self.body.addWidget(quick)
        self.status = label('●  Готов к работе', 'secondary')
        self.body.addWidget(self.status)
        self.body.addStretch()
