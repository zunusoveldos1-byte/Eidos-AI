"""Reparent existing forms instead of cloning controls or controllers."""
from eidos.ui.localized import QLabel, QTabWidget
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
    destinations = {'Календарь': window.tools.tabs, 'Skills': window.tools.tabs,
                    'Модель': settings.tabs, 'Подключения': settings.tabs}
    for name, target in destinations.items():
        page = ui.sections[name]
        ui.tabs.removeTab(ui.tabs.indexOf(page))
        target.addTab(page, 'Возможности' if name == 'Skills' else name)
    for name in ('Память', 'Профиль'):
        page = ui.sections[name]
        ui.tabs.removeTab(ui.tabs.indexOf(page))
        page.setParent(ui)
        page.hide()
    ui.tabs.tabBar().hide()
    documents = Page('Документы', 'Доступ только к выбранным файлам и рабочей папке')
    documents.body.addWidget(label('Выберите документы или рабочую папку. Доступ ограничен вашим выбором; запись требует подтверждения.', 'secondary'))
    documents.body.addWidget(ResponsiveRow([ui.select_files, ui.select_folder, ui.forget_files], threshold=600))
    documents.body.addWidget(ui.grants)
    documents.body.addWidget(ResponsiveRow([ui.document_read_button, ui.document_write_button], threshold=600))
    ui.history.setPlaceholderText('Результат чтения документа или выполнения инструмента')
    documents.body.addWidget(ui.history)
    documents.body.addWidget(ui.stop)
    documents.body.addStretch()
    window.tools.tabs.insertTab(0, documents, 'Документы')
    quick = Page('Windows и браузер', 'Операции выполняет общий агент')
    for name, tool, args in [('Открыть блокнот', 'open_notepad', {}),
                             ('Параметры звука Windows', 'windows_settings', {'page': 'sound'}),
                             ('Открыть YouTube', 'open_url', {'url': 'https://www.youtube.com'})]:
        control = button(name)
        control.clicked.connect(lambda checked=False, t=tool, a=args: window._start_agent_task('tool', (t, a)))
        quick.body.addWidget(control)
    quick.body.addWidget(label('Команды также доступны голосом. Подключения и модель настраиваются в «Настройках».', 'muted'))
    screenshot_folder = button('Папка скриншотов')
    def choose_screenshot_folder():
        from PyQt6.QtWidgets import QFileDialog
        from dataclasses import replace
        path = QFileDialog.getExistingDirectory(window, 'Папка скриншотов', window.agent_service.settings.screenshot_folder)
        if path:
            window.agent_service.save_settings(replace(window.agent_service.settings, screenshot_folder=path))
            ui.feedback.setText('Папка скриншотов сохранена.')
    screenshot_folder.clicked.connect(choose_screenshot_folder)
    quick.body.addWidget(screenshot_folder)
    quick.body.addWidget(ui.input)
    ui.input.show()
    execute_command = button('Выполнить команду', 'send', True)
    execute_command.clicked.connect(lambda: window._start_agent_task('chat', ui.input.toPlainText()))
    quick.body.addWidget(execute_command)
    from .assistant import text_area
    window.command_output = text_area(160, True)
    window.command_output.setAccessibleName('Ответ на системную команду')
    quick.body.addWidget(window.command_output)
    quick.body.addStretch()
    window.tools.tabs.insertTab(0, quick, 'Windows и браузер')
    window.tools.tabs.setCurrentIndex(0)
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
    settings.tabs.addTab(voice.config_tabs, 'Голос')
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
    voice.storage.setParent(ui)
    voice.storage.hide()
    settings.profile_row.hide()
    settings.profile_buttons.hide()
    ui.profile.memory.hide()
    from .settings_layout import rebuild
    rebuild(window)
