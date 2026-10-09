from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from ..components import Card, Page, ResponsiveRow, TextCard, button, combo, label
from ..icons import icon
from ..mascot import Mascot


class TranslationPage(Page):
    def __init__(self) -> None:
        super().__init__('Перевод экрана', 'Выберите область экрана и переведите текст')
        self.badge()
        source, target = Card(margins=12), Card(margins=12)
        source.body.setSpacing(4)
        target.body.setSpacing(4)
        source.body.addWidget(label('С языка', 'muted'))
        target.body.addWidget(label('На язык', 'muted'))
        self.source = combo()
        self.source.addItem('Автоопределение')
        self.target = combo()
        self.target.addItem('Русский')
        for control, card in [(self.source, source), (self.target, target)]:
            control.setEnabled(False)
            control.setToolTip('Выбор языка появится после подключения OCR и перевода')
            card.body.addWidget(control)
        self.select_button = button('Выбрать область', 'scan', True)
        self.select_button.setEnabled(False)
        self.select_button.setToolTip('Модуль OCR пока не подключён')
        self.select_button.setMinimumHeight(46)
        self.body.addWidget(ResponsiveRow([source, target, self.select_button], threshold=660))
        self.original = TextCard('Исходный текст', 'Здесь появится распознанный текст', centered=True)
        self.translated = TextCard('Перевод', 'Здесь появится перевод', centered=True)
        self.body.addWidget(ResponsiveRow([self.original, self.translated], threshold=640))
        help_card = Card(margins=20)
        self.mascot = Mascot(145)
        steps = []
        for index, (name, title, detail) in enumerate([
            ('scan', 'Выберите область', 'Укажите область экрана с текстом'),
            ('file', 'Распознайте текст', 'Текст будет автоматически распознан'),
            ('languages', 'Получите перевод', 'Сразу получите перевод на выбранный язык'),
        ], 1):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            image = QLabel()
            image.setPixmap(icon(name, '#A8B7AE', 30).pixmap(30, 30))
            layout.addWidget(image)
            layout.addWidget(label(f'{index}. {title}', 'h3'))
            layout.addWidget(label(detail, 'muted'))
            steps.append(widget)
        help_copy = QWidget()
        texts = QVBoxLayout(help_copy)
        texts.setContentsMargins(0, 0, 0, 0)
        texts.addWidget(label('Как это работает', 'h2'))
        texts.addWidget(ResponsiveRow(steps, threshold=520))
        row = QHBoxLayout()
        row.addWidget(self.mascot)
        row.addWidget(help_copy, 1)
        help_card.body.addLayout(row)
        self.body.addWidget(help_card)
        self.body.addStretch()
