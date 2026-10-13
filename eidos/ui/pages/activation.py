from PyQt6.QtCore import pyqtSignal
from ..components import Page, Card, button, label


class ActivationPage(Page):
    save_requested = pyqtSignal()

    def __init__(self, settings):
        super().__init__('Активация голосом', '«Эйдос» и команда — одной фразой')
        self.body.addWidget(settings.wake_card)
        examples = Card()
        examples.heading('Попробуйте сказать', 'mic')
        for text in ('Эйдос, открой блокнот', 'Эйдос, открой YouTube', 'Эйдос, сделай звук потише',
                     'Эйдос, переведи область экрана', 'Эйдос, прочитай перевод'):
            examples.body.addWidget(label('«' + text + '»', 'secondary'))
        examples.body.addWidget(label('Начало фразы сохраняется в коротком аудиобуфере. При озвучке и её паузе активация временно отключается.', 'muted'))
        self.body.addWidget(examples)
        save = button('Сохранить настройки активации', primary=True)
        save.clicked.connect(self.save_requested)
        self.body.addWidget(save)
        self.body.addStretch()
