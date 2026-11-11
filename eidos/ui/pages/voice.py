"""Minimal voice stage; existing controls are owned by settings/dialogue."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout
from eidos.ui.localized import QPlainTextEdit, QWidget
from ..components import Card, Page, ResponsiveRow, TextCard, Toggle, button, combo, icon_button, label
from ..voice_page_orb import VoicePageOrb


class VoicePage(Page):
    action_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    mute_requested = pyqtSignal()
    compact_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__('Голос', '')
        self.setObjectName('voicePage')
        self.content.setObjectName('voiceContent')
        self.scroll.setObjectName('voiceScroll')
        self.scroll.viewport().setObjectName('voiceViewport')
        self.setStyleSheet('QWidget#voicePage, QWidget#voiceContent, QWidget#voiceViewport, QScrollArea#voiceScroll {background:#0D1110;}')
        self.header.itemAt(0).layout().itemAt(1).widget().hide()
        self.stage = QWidget()
        layout = QVBoxLayout(self.stage)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.mascot = self.action_button = VoicePageOrb(250)
        self.action_button.clicked.connect(self.action_requested)
        layout.addWidget(self.mascot, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.title = label('Микрофон выключен', 'h2', True)
        self.operation = label('Нажмите, чтобы включить', 'secondary', True)
        layout.addWidget(self.title)
        layout.addWidget(self.operation)
        self.body.addStretch(1)
        self.body.addWidget(self.stage)
        self.body.addStretch(1)
        self._operation_message = ''
        self.mascot.presentation_changed.connect(self._presentation)
        # Compatibility references keep signal/controller wiring stable. These
        # editors are reparented to the dialogue's hidden storage, not shown twice.
        self.storage = QWidget(self)
        self.storage.hide()
        self.recognized = TextCard('Вы сказали', 'Распознанная команда', 'user')
        self.answer = TextCard('Ответ Eidos', 'Ответ появится здесь', 'eidos')
        for widget in (self.recognized, self.answer):
            widget.setParent(self.storage)
            widget.hide()
        self.response_status = label('', 'muted')
        self.input_level = label('', 'muted')
        self.stop_button = button('Остановить', 'stop')
        self.mute_button = button('Отключить микрофон', 'mic')
        for widget in (self.response_status, self.input_level, self.stop_button, self.mute_button):
            widget.setParent(self.storage)
            widget.hide()
        self.stop_button.clicked.connect(self.stop_requested)
        self.mute_button.clicked.connect(self.mute_requested)
        self.settings_panel = Card(margins=14)
        self.settings_panel.setParent(self.storage)
        self.microphone = combo()
        self.microphone.setAccessibleName('Микрофон для записи')
        self.refresh_button = icon_button('refresh', 'Обновить список микрофонов')
        self.refresh_button.clicked.connect(self.refresh_requested)
        self.settings_panel.body.addWidget(ResponsiveRow([self.microphone, self.refresh_button], threshold=450))
        self.speak = Toggle('Озвучивать ответы')
        self.settings_panel.body.addWidget(self.speak)
        self.details_button = button('Журнал событий', 'list')
        self.details_button.setCheckable(True)
        self.journal = QPlainTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setMaximumBlockCount(100)
        self.journal.setFixedHeight(125)
        self.journal.hide()
        self.details_button.toggled.connect(self.journal.setVisible)
        self.settings_panel.body.addWidget(self.details_button)
        self.settings_panel.body.addWidget(self.journal)
        self.settings_panel.hide()

    def _presentation(self):
        title, hint = self.mascot.copy()
        self.title.setText(title)
        self.title.setToolTip(self.mascot.microphone_error or self._operation_message)
        self.operation.setText(hint)
        self.operation.setVisible(bool(hint))

    def show_state(self, state, message):
        visual = {'idle': 'ready', 'starting': 'listening', 'recording': 'listening',
                  'playing': 'speaking', 'paused': 'paused', 'error': 'error'}.get(state, 'thinking')
        self.set_operation(message)
        self.mascot.set_state(visual)

    def set_operation(self, message):
        self._operation_message = message
        self.mascot.set_message(message)

    def set_microphone(self, state, error=''):
        self.mascot.set_microphone(state, error)
