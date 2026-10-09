"""Assistant workspace; technical settings stay inside tabs, not the sidebar."""
from PyQt6.QtCore import QDateTime, Qt
from PyQt6.QtWidgets import (QCheckBox, QDateTimeEdit, QDialog, QHBoxLayout, QLineEdit,
                            QListWidget, QListWidgetItem, QPlainTextEdit, QSpinBox,
                            QTabWidget, QVBoxLayout, QWidget, QLabel, QScrollArea)
from ..components import Page, Card, ResponsiveRow, button, combo, label
from ..mascot import Mascot
from eidos.agent.settings import PROFESSIONS, REMOTE_PERMISSIONS


def edit(placeholder=''):
    result = QLineEdit()
    result.setPlaceholderText(placeholder)
    result.setMinimumWidth(0)
    result.setAccessibleName(placeholder)
    return result


def text_area(height=120, readonly=False):
    result = QPlainTextEdit()
    result.setReadOnly(readonly)
    result.setMinimumHeight(height)
    result.setMaximumBlockCount(1000)
    return result


def row(layout, *widgets):
    layout.addWidget(ResponsiveRow(list(widgets), threshold=650, spacing=10))


class ProfileForm(Card):
    def __init__(self, settings):
        super().__init__()
        self.heading('Чем вы занимаетесь?', 'user')
        self.body.addWidget(label('Можно выбрать несколько вариантов. Это помогает подобрать подсказки и не ограничивает функции.', 'muted'))
        self.professions = QListWidget()
        self.professions.setMinimumHeight(190)
        for name in PROFESSIONS:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in settings.professions else Qt.CheckState.Unchecked)
            self.professions.addItem(item)
        self.body.addWidget(self.professions)
        self.name = edit('Как к вам обращаться? Необязательно')
        self.name.setText(settings.name)
        self.language = combo()
        self.language.setEditable(True)
        self.language.addItems(['Русский', 'English'])
        self.language.setCurrentText(settings.language)
        self.tasks = text_area(70)
        self.tasks.setMaximumHeight(95)
        self.tasks.setPlaceholderText('Основные задачи — необязательно')
        self.tasks.setPlainText(settings.tasks)
        self.memory = QCheckBox('Включить постоянную память на этом компьютере')
        self.memory.setChecked(settings.memory_enabled)
        self.body.addWidget(self.name)
        row(self.body, label('Язык ответов'), self.language)
        self.body.addWidget(self.tasks)
        self.body.addWidget(self.memory)
        self.body.addWidget(label('Пароли и ключи вводятся только в «Подключениях». Память — поиск по данным; веса модели не переобучаются.', 'muted'))

    def values(self):
        return dict(name=self.name.text().strip(), language=self.language.currentText().strip(), tasks=self.tasks.toPlainText().strip(),
                    memory_enabled=self.memory.isChecked(), onboarding_done=True,
                    professions=[self.professions.item(i).text() for i in range(self.professions.count())
                                 if self.professions.item(i).checkState() == Qt.CheckState.Checked])


class Onboarding(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle('Знакомство с Eidos')
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(570, 660)
        self.setMinimumSize(400, 380)
        layout = QVBoxLayout(self)
        self.form = ProfileForm(settings)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.form)
        layout.addWidget(self.scroll, 1)
        self.skip = button('Пропустить')
        self.save = button('Начать', primary=True)
        row(layout, self.skip, self.save)
        self.skip.clicked.connect(self.reject)
        self.save.clicked.connect(self.accept)


class AssistantPage(Page):
    def __init__(self, service):
        super().__init__('Ассистент', 'Диалог, инструменты и память — под вашим контролем')
        self.service = service
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setMinimumHeight(260)
        self.body.addWidget(self.tabs, 1)
        self.feedback = label('', 'muted')
        self.body.addWidget(self.feedback)
        self._chat()
        self._memory()
        self._calendar()
        self._skills()
        self._connections()
        self._model()
        self._profile()

    def tab(self, title, subtitle):
        page = Page(title, subtitle)
        for heading in page.findChildren(QLabel):
            if heading.objectName() == 'h1':
                heading.setObjectName('h2')
            elif heading.objectName() == 'subtitle':
                heading.setObjectName('muted')
        self.tabs.addTab(page, title)
        return page

    def _chat(self):
        page = self.tab('Диалог', 'Начните с вопроса или команды Windows. Микрофон здесь не включается.')
        self.chat_page = page
        header = Card(margins=14)
        self.mascot = Mascot(72)
        self.task_status = label('Готов к запросу', 'h2')
        self.stop = button('Остановить')
        self.stop.setEnabled(False)
        row(header.body, self.mascot, self.task_status, self.stop)
        page.body.addWidget(header)
        self.profile_hint = label('', 'muted')
        page.body.addWidget(self.profile_hint)
        self.history = text_area(190, True)
        self.history.setObjectName('conversation')
        self.history.setPlaceholderText('История текущего диалога. Постоянная память включается отдельно.')
        self.history.setAccessibleName('История диалога')
        page.body.addWidget(self.history)
        self.input = text_area(70)
        self.input.setObjectName('conversation')
        self.input.setMaximumHeight(110)
        self.input.setPlaceholderText('Например: «Сделай громкость 30 процентов» или «Помоги составить план»')
        self.input.setAccessibleName('Ваш запрос')
        page.body.addWidget(self.input)
        self.incognito = QCheckBox('Разговор без сохранения')
        self.send = button('Отправить', 'message', True)
        row(page.body, self.incognito, self.send)
        self.select_files = button('Выбрать файлы', 'file')
        self.select_folder = button('Рабочая папка')
        self.forget_files = button('Закрыть доступ к файлам')
        row(page.body, self.select_files, self.select_folder, self.forget_files)
        self.grants = label('Файлы и папки не выбраны', 'muted')
        page.body.addWidget(self.grants)
        self.document_read_button = button('Прочитать выбранный документ')
        self.document_write_button = button('Создать документ из текста')
        row(page.body, self.document_read_button, self.document_write_button)
        self.journal = text_area(90, True)
        self.journal.setObjectName('journal')
        self.journal.setMaximumHeight(125)
        self.journal.setMaximumBlockCount(100)
        self.journal.setPlaceholderText('Журнал действий (без текста разговоров и ключей)')
        page.body.addWidget(self.journal)

    def _memory(self):
        page = self.tab('Память', 'Локальная SQLite-память. Факты добавляете и исправляете вы; догадки модели не становятся фактами.')
        self.memory_enabled = QCheckBox('Сохранять диалоги и использовать релевантную память')
        self.memory_enabled.setChecked(self.service.settings.memory_enabled)
        page.body.addWidget(self.memory_enabled)
        self.memory_kind = combo()
        for title, kind in [('Все записи', None), ('Диалоги', 'dialogue'), ('Профиль', 'profile'), ('Предпочтения', 'preference'), ('Факты проектов', 'project'), ('Итоги задач', 'summary')]:
            self.memory_kind.addItem(title, kind)
        self.memory_search = edit('Поиск по словам')
        self.memory_refresh = button('Обновить', 'refresh')
        row(page.body, self.memory_kind, self.memory_search, self.memory_refresh)
        self.memory_list = QListWidget()
        self.memory_list.setMinimumHeight(190)
        page.body.addWidget(self.memory_list)
        self.memory_edit = text_area(100)
        self.memory_edit.setPlaceholderText('Добавьте подтверждённый факт или исправьте выбранную запись')
        self.memory_source = edit('Источник: например «Я сообщил вручную»')
        self.memory_source.setText('Пользователь: ручная запись')
        page.body.addWidget(self.memory_edit)
        page.body.addWidget(self.memory_source)
        self.fact_kind = combo()
        self.fact_kind.addItem('Факт проекта', 'project')
        self.fact_kind.addItem('Предпочтение', 'preference')
        self.fact_kind.addItem('Профиль', 'profile')
        self.memory_save = button('Сохранить запись', primary=True)
        self.memory_new = button('Новая запись')
        self.memory_delete = button('Удалить выбранную')
        row(page.body, self.fact_kind, self.memory_new, self.memory_save, self.memory_delete)
        self.history_clear = button('Очистить историю')
        self.memory_clear = button('Удалить всю память')
        row(page.body, self.history_clear, self.memory_clear)

    def _calendar(self):
        page = self.tab('Календарь', 'Локальные события. Напоминания показываются, пока Eidos открыт. Внешней синхронизации нет.')
        self.calendar_list = QListWidget()
        self.calendar_list.setMinimumHeight(170)
        page.body.addWidget(self.calendar_list)
        self.event_title = edit('Название события')
        self.event_start = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.event_start.setCalendarPopup(True)
        self.event_start.setDisplayFormat('dd.MM.yyyy HH:mm')
        self.event_zone = edit('Часовой пояс IANA')
        self.event_zone.setText(self.service.settings.timezone)
        self.event_reminder = QSpinBox()
        self.event_reminder.setRange(0, 10080)
        self.event_reminder.setValue(10)
        self.event_reminder.setSuffix(' мин. до начала')
        page.body.addWidget(self.event_title)
        row(page.body, self.event_start, self.event_zone, self.event_reminder)
        self.event_create = button('Создать', primary=True)
        self.event_update = button('Изменить')
        self.event_delete = button('Удалить')
        self.event_refresh = button('Обновить', 'refresh')
        row(page.body, self.event_create, self.event_update, self.event_delete, self.event_refresh)

    def _skills(self):
        page = self.tab('Skills', 'Каталог возможностей. Разрешения всегда проверяет общий harness.')
        self.skills_list = QListWidget()
        self.skills_list.setMinimumHeight(390)
        self.skill_detail = label('', 'muted')
        page.body.addWidget(self.skills_list)
        page.body.addWidget(self.skill_detail)

    def _connections(self):
        page = self.tab('Подключения', 'Только официальные bot API. Секреты сохраняются в Windows Credential Manager.')
        self.secrets_edits = {}
        self.bot_enabled = {}
        self.bot_users = {}
        self.bot_channels = {}
        self.bot_tests = {}
        for kind, title in [('telegram','Telegram Bot'), ('discord','Discord Bot'), ('openai','OpenAI (необязательно)'), ('brave','Brave Search API (необязательно)')]:
            card = Card()
            card.heading(title, 'message')
            secret = edit('Bot token' if kind in ('telegram','discord') else 'API key')
            secret.setEchoMode(QLineEdit.EchoMode.Password)
            secret.setPlaceholderText('Новый секрет; пустое поле сохраняет прежний')
            self.secrets_edits[kind] = secret
            card.body.addWidget(secret)
            if kind in ('telegram','discord'):
                enabled = QCheckBox('Получать сообщения от разрешённых пользователей')
                enabled.setChecked(getattr(self.service.settings, kind+'_enabled'))
                users = edit('Разрешённые user IDs через запятую')
                users.setText(', '.join(getattr(self.service.settings, kind+'_users')))
                channels = edit('Разрешённые chat / channel IDs через запятую')
                channels.setText(', '.join(getattr(self.service.settings, kind+'_channels')))
                test = button('Проверить bot API')
                self.bot_enabled[kind], self.bot_users[kind], self.bot_channels[kind], self.bot_tests[kind] = enabled, users, channels, test
                card.body.addWidget(enabled)
                card.body.addWidget(users)
                card.body.addWidget(channels)
                card.body.addWidget(test)
            elif kind == 'openai':
                card.body.addWidget(label('Облако используется только при выборе OpenAI во вкладке «Модель». Запрос и выбранный контекст тогда отправляются в OpenAI.', 'muted'))
            else:
                card.body.addWidget(label('Для автоматического получения источников выберите Brave API как поисковик во вкладке «Модель». Поисковые запросы отправляются в Brave; ключ используется только в заголовке HTTP.', 'muted'))
                self.search_test = button('Проверить Search API')
                card.body.addWidget(self.search_test)
            page.body.addWidget(card)
        permissions = Card()
        permissions.heading('Удалённый доступ', 'settings')
        permissions.body.addWidget(label('По умолчанию отключён. Только пользователи И каналы из обоих списков. Локальные файлы, память и календарь удалённым каналам недоступны. Ответ бота отправляется после подтверждения в окне Eidos. Файлы и вложения не принимаются (лимит 0 байт); текст — до 2000 символов.', 'muted'))
        self.remote_checks = {}
        names = ('Параметры Windows', 'Громкость и mute', 'Разрешённые приложения', 'Открытие URL')
        for capability, title in zip(REMOTE_PERMISSIONS, names):
            check = QCheckBox(title)
            check.setChecked(capability in self.service.settings.remote_permissions)
            self.remote_checks[capability] = check
            permissions.body.addWidget(check)
        page.body.addWidget(permissions)
        self.connections_save = button('Сохранить подключения', primary=True)
        self.secret_delete = combo()
        self.secret_delete.addItems(['telegram', 'discord', 'openai', 'brave'])
        self.secret_delete_button = button('Удалить секрет')
        row(page.body, self.connections_save, self.secret_delete, self.secret_delete_button)
        page.body.addWidget(label('Discord: пригласите бота на сервер с View Channel / Read Message History / Send Messages; включите Message Content Intent. Проверка токена не проверяет разрешения конкретного канала. Внешний календарь: адаптер пока не реализован.', 'muted'))

    def _model(self):
        page = self.tab('Модель', 'Локальный Ollama или опциональный облачный провайдер')
        settings = self.service.settings
        self.provider = combo()
        self.provider.addItem('Ollama — локально', 'ollama')
        self.provider.addItem('OpenAI — облако', 'openai')
        self.provider.setCurrentIndex(self.provider.findData(settings.provider))
        self.model_name = edit('Имя модели Ollama')
        self.model_name.setText(settings.model)
        self.ollama_url = edit('Локальный адрес Ollama')
        self.ollama_url.setText(settings.ollama_url)
        self.cloud_model = edit('Модель OpenAI')
        self.cloud_model.setText(settings.cloud_model)
        self.context_size = QSpinBox()
        self.context_size.setRange(1024, 8192)
        self.context_size.setSingleStep(1024)
        self.context_size.setValue(settings.context_size)
        row(page.body, label('Провайдер'), self.provider)
        row(page.body, label('Ollama-модель'), self.model_name)
        row(page.body, label('Адрес'), self.ollama_url)
        row(page.body, label('Облачная модель'), self.cloud_model)
        row(page.body, label('Контекст Ollama, токенов'), self.context_size)
        self.search_provider = combo()
        self.search_provider.addItem('DuckDuckGo', 'duckduckgo')
        self.search_provider.addItem('Bing', 'bing')
        self.search_provider.addItem('Brave Search API — источники', 'brave')
        self.search_provider.setCurrentIndex(self.search_provider.findData(settings.search_provider))
        row(page.body, label('Поисковик'), self.search_provider)
        self.model_save = button('Сохранить модель', primary=True)
        self.server_start = button('Запустить Ollama')
        self.model_pull = button('Загрузить модель')
        row(page.body, self.model_save, self.server_start, self.model_pull)
        self.model_test = button('Проверить ответ и tool calling')
        self.hardware_test = button('Диагностика ноутбука')
        row(page.body, self.hardware_test, self.model_test)
        page.body.addWidget(label('Для RTX 3050 6 ГБ / RAM 16 ГБ: Qwen3 4B Q4_K_M (2,5 ГБ), контекст 4096, GPU. Облегчённый: Qwen3 1.7B (1,4 ГБ), 2048. Thinking отключён. Скорость определяется измерением. Whisper по умолчанию CPU int8; свободную RAM проверяйте перед совместной работой.', 'muted'))
        self.hardware_display = text_area(150, True)
        self.hardware_display.setPlaceholderText('Здесь появятся реальные результаты диагностики / проверки модели')
        page.body.addWidget(self.hardware_display)
        self.app_add = button('Добавить разрешённое EXE')
        self.app_remove = button('Удалить приложение из списка')
        self.apps_list = combo()
        row(page.body, self.apps_list, self.app_add, self.app_remove)

    def _profile(self):
        page = self.tab('Профиль', 'Ответы можно изменить в любое время или оставить пустыми.')
        self.profile = ProfileForm(self.service.settings)
        page.body.addWidget(self.profile)
        self.profile_save = button('Сохранить профиль', primary=True)
        page.body.addWidget(self.profile_save)
