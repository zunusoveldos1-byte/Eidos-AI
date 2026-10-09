from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from ..components import Card, Page, ResponsiveRow, TextCard, Toggle, button, combo, icon_button, label
from ..icons import icon
from ..mascot import Mascot


class VoicePage(Page):
    action_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__('Голосовой помощник', 'Запишите команду и получите ответ')
        self.microphone = combo()
        self.microphone.setMaximumWidth(270)
        self.microphone.setAccessibleName('Микрофон для записи')
        self.microphone.setToolTip('Выберите микрофон для следующей записи')
        self.refresh_button = icon_button('refresh', 'Обновить список микрофонов')
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.header.addWidget(self.microphone)
        self.header.addWidget(self.refresh_button)
        record = Card(margins=20)
        record.body.setSpacing(10)
        record.setMinimumHeight(430)
        self.mascot = Mascot(150)
        record.body.addWidget(self.mascot, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = label('Готов к записи', 'h2', True)
        record.body.addWidget(self.title)
        self.operation = label('Нажмите кнопку и произнесите команду', 'secondary', True)
        self.operation.setMinimumHeight(30)
        record.body.addWidget(self.operation)
        self.action_button = button('Начать запись', 'mic', True)
        self.action_button.setMinimumHeight(34)
        self.action_button.clicked.connect(self.action_requested)
        record.body.addWidget(self.action_button)
        line = QFrame()
        line.setObjectName('line')
        record.body.addWidget(line)
        toggle_row = QHBoxLayout()
        self.speak = Toggle('Озвучивать ответы')
        toggle_row.addWidget(self.speak, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(label('Озвучивать ответы'))
        text.addWidget(label('Eidos будет зачитывать ответы вслух', 'muted'))
        toggle_row.addLayout(text, 1)
        record.body.addLayout(toggle_row)
        output = QWidget()
        output_layout = QVBoxLayout(output)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(16)
        self.recognized = TextCard('Вы сказали', 'Здесь появится распознанная команда', 'user')
        self.answer = TextCard('Ответ Eidos', 'Здесь появится ответ ассистента', 'eidos')
        for panel in (self.recognized, self.answer):
            panel.text.setMinimumHeight(90)
            panel.text.setMaximumHeight(140)
        output_layout.addWidget(self.recognized, 1)
        output_layout.addWidget(self.answer, 1)
        self.body.addWidget(ResponsiveRow([record, output], threshold=690))
        hints = Card(margins=14)
        hints.body.setSpacing(8)
        hints.heading('Попробуйте сказать', 'message')
        for heading in hints.findChildren(QWidget):
            if heading.objectName() == 'h2':
                heading.setObjectName('h3')
        chips = []
        for command in ('Привет', 'Который час?', 'Какая сегодня дата?', 'Помощь'):
            chip = button(command)
            chip.setObjectName('chip')
            chip.setToolTip('Пример голосовой команды. Для записи нажмите «Начать запись».')
            # A hint never fakes STT or triggers a hidden recording.
            chip.clicked.connect(lambda checked=False, text=command: self.operation.setText(f'Скажите «{text}» после начала записи.'))
            chips.append(chip)
        hints.body.addWidget(ResponsiveRow(chips, threshold=610, spacing=10))
        self.details_button = button('Подробности', 'list')
        self.details_button.setObjectName('details')
        self.details_button.setCheckable(True)
        self.journal = QPlainTextEdit()
        self.journal.setObjectName('journal')
        self.journal.setReadOnly(True)
        self.journal.setMaximumBlockCount(100)
        self.journal.setFixedHeight(125)
        self.journal.setAccessibleName('Журнал событий')
        self.journal.hide()
        hints.body.addWidget(self.details_button)
        hints.body.addWidget(self.journal)
        self.details_button.toggled.connect(self.journal.setVisible)
        self.body.addWidget(hints)
        self.body.addWidget(label('Запись только по кнопке · STT локально после загрузки · Озвучивание онлайн', 'muted'))
        self.body.addStretch()

    def show_state(self, state: str, message: str) -> None:
        titles = {
            'idle': 'Готов к записи', 'starting': 'Подключение микрофона',
            'recording': 'Слушаю вас', 'loading': 'Загрузка модели',
            'transcribing': 'Распознаю речь', 'synthesizing': 'Подготовка озвучки',
            'playing': 'Eidos отвечает', 'error': 'Не удалось выполнить операцию',
            'closing': 'Завершение работы',
        }
        self.title.setText(titles.get(state, 'Голосовой помощник'))
        self.operation.setText(message)
        mascot = 'listening' if state == 'recording' else 'error' if state == 'error' else 'ready' if state == 'idle' else 'thinking'
        self.mascot.set_state(mascot)
        active = state not in {'idle', 'error'}
        self.action_button.setText('Остановить' if active else 'Начать запись')
        self.action_button.setIcon(icon('mic', '#061B12'))
