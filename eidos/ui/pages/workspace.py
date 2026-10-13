"""Reparent existing forms instead of cloning controls or controllers."""
from PyQt6.QtWidgets import QLabel, QTabWidget
from ..components import Page, ResponsiveRow, button, label


class SectionPage(Page):
    def __init__(self, title, subtitle):
        super().__init__(title, subtitle)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.body.addWidget(self.tabs, 1)


def reorganize(window):
    ui, settings, voice = window.assistant, window.settings, window.voice
    window.tools = SectionPage('Инструменты', 'Доступные действия, документы и локальный календарь')
    window.memory = SectionPage('Память', 'Ваш профиль и сведения, которые вы разрешили сохранять')
    settings.tabs = QTabWidget()
    settings.tabs.setUsesScrollButtons(True)
    settings.tabs.addTab(settings.general_page, 'Общие')
    for heading in settings.general_page.findChildren(QLabel):
        if heading.objectName() == 'h1':
            heading.setObjectName('h2')
        elif heading.objectName() == 'subtitle':
            heading.setObjectName('muted')
    settings.body.addWidget(settings.tabs)
    settings.tabs.currentChanged.connect(lambda index: settings.footer.setVisible(index == 0))
    settings.feedback.hide()
    settings.feedback = ui.feedback
    destinations = {'Память': window.memory.tabs, 'Профиль': window.memory.tabs,
                    'Календарь': window.tools.tabs, 'Skills': window.tools.tabs,
                    'Модель': settings.tabs, 'Подключения': settings.tabs}
    for name, target in destinations.items():
        page = ui.sections[name]
        ui.tabs.removeTab(ui.tabs.indexOf(page))
        target.addTab(page, 'Возможности' if name == 'Skills' else name)
    ui.tabs.tabBar().hide()
    for item_index in (0, 1):
        ui.sections['Диалог'].header.itemAt(0).layout().itemAt(item_index).widget().hide()
    documents = Page('Документы', 'Доступ только к выбранным файлам и рабочей папке')
    documents.body.addWidget(label('Приложите файл в «Диалоге», затем прочитайте его здесь. Для создания выберите рабочую папку; содержимое берётся из поля вашего запроса.', 'secondary'))
    documents.body.addWidget(ResponsiveRow([ui.document_read_button, ui.document_write_button], threshold=600))
    documents.body.addStretch()
    window.tools.tabs.insertTab(0, documents, 'Документы')
    quick = Page('Windows и браузер', 'Операции выполняет общий агент')
    for name, tool, args in [('Открыть блокнот', 'open_notepad', {}),
                             ('Параметры звука Windows', 'windows_settings', {'page': 'sound'}),
                             ('Открыть YouTube', 'open_url', {'url': 'https://www.youtube.com'})]:
        control = button(name)
        control.clicked.connect(lambda checked=False, t=tool, a=args: window._start_agent_task('tool', (t, a)))
        quick.body.addWidget(control)
    quick.body.addWidget(label('Поиск и чтение публичных страниц доступны через диалог. Подключения и модель настраиваются в «Настройках».', 'muted'))
    quick.body.addStretch()
    window.tools.tabs.insertTab(0, quick, 'Windows и браузер')
    window.tools.tabs.setCurrentIndex(0)
    window.memory.tabs.setCurrentIndex(0)
    memory_page = ui.sections['Память']
    ui.memory_new.setText('Добавить запись')
    ui.memory_new.setObjectName('primary')
    memory_page.header.addWidget(ui.memory_new)
    ui.memory_new.clicked.connect(lambda: (memory_page.scroll.ensureWidgetVisible(ui.memory_edit), ui.memory_edit.setFocus()))
    voice.config_tabs = QTabWidget()
    voice.config_tabs.setUsesScrollButtons(True)
    voice_parameters = Page('Микрофон и озвучка', 'Выбор устройства, голос и параметры ответа')
    voice_parameters.body.addWidget(voice.settings_panel)
    voice.settings_panel.show()
    voice_parameters.body.addWidget(settings.voice_card)
    voice_parameters.body.addWidget(settings.speech_card)
    activation = Page('Активация голосом', 'Слово «Эйдос» обрабатывается локально после настройки модели')
    activation.body.addWidget(settings.wake_card)
    voice.config_tabs.addTab(voice_parameters, 'Устройство и голос')
    voice.config_tabs.addTab(activation, 'Активация голосом')
    voice.settings_button.setText('Устройство, голос и активация')
    voice.settings_button.toggled.disconnect()
    voice.settings_button.toggled.connect(voice.config_tabs.setVisible)
    voice.config_tabs.hide()
    voice.body.insertWidget(voice.body.indexOf(voice.settings_button) + 1, voice.config_tabs)
    for name in ('tts_voice', 'tts_provider', 'sapi_voice', 'tts_rate', 'tts_volume'):
        setattr(voice, name, getattr(settings, name))
    save_voice = button('Сохранить параметры голоса', primary=True)
    save_voice.clicked.connect(window._save_settings)
    voice_parameters.body.addWidget(save_voice)
    save_activation = button('Сохранить параметры активации', primary=True)
    save_activation.clicked.connect(window._save_settings)
    activation.body.addWidget(save_activation)
    settings.microphone_row.hide()
    settings.speak_row.hide()
    settings.microphone = voice.microphone
    settings.speak = voice.speak
    window.memory.tabs.widget(1).body.insertWidget(0, settings.profile_row)
    window.memory.tabs.widget(1).body.insertWidget(1, settings.profile_buttons)
    ui.profile.memory.hide()
