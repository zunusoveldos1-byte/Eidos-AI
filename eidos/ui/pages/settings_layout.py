"""Compact forms reuse the existing controls and their signal bindings."""
from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLayout, QSizePolicy
from PyQt6.QtWidgets import QVBoxLayout
from eidos.ui.localized import QWidget, QLabel
from ..components import Card, Page, ResponsiveRow, button, label


def detach(owner, controls):
    for control in controls:
        control.setParent(owner)
        control.hide()


def clear_page(page, keep_header=False):
    def hide_layout(layout):
        for index in range(layout.count()):
            child = layout.itemAt(index)
            if child.widget(): child.widget().hide()
            elif child.layout(): hide_layout(child.layout())
    while page.body.count():
        item = page.body.takeAt(0)
        if keep_header and item.layout() is page.header:
            continue
        if item.widget():
            item.widget().hide()
        elif item.layout():
            hide_layout(item.layout())
    page.body.setContentsMargins(12, 12, 12, 12)
    page.body.setSpacing(8)
    page.body.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
    if keep_header:
        page.body.addLayout(page.header)


def form(title, rows):
    card = Card(margins=12)
    card.body.setSpacing(6)
    card.heading(title)
    host = QWidget()
    layout = QFormLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    card.rows = {}
    for text, control in rows:
        caption = label(text)
        caption.setWordWrap(True)
        control.setMinimumWidth(0)
        control.show()
        layout.addRow(caption, control)
        card.rows[control] = (caption, control)
    card.form = layout
    card.body.addWidget(host)
    return card


def row(*controls):
    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for control in controls:
        layout.addWidget(control)
        control.show()
    return host


def column(*controls):
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    for control in controls: layout.addWidget(control)
    layout.addStretch()
    return host


def rebuild(window):
    s, ui, voice = window.settings, window.assistant, window.voice
    names = ('startup startup_status on_top language mascot_visible character_button '
             'close_to_tray start_in_tray floating_enabled floating_pinned reduce_animations '
             'voice_hotkey_enabled voice_hotkey tts_voice communication_style tts_provider '
             'sapi_voice tts_rate tts_volume voice_response_brief sample_button voices_button '
             'stop_speech_button wake_word_enabled wake_keyword_path wake_model_path '
             'wake_access_key wake_sensitivity wake_secret_button wake_status stt_engine '
             'vosk_model_path vosk_select model voice_sensitivity voice_max_seconds device '
             'theme accent_color animation hotkeys_enabled capture_hotkey repeat_hotkey '
             'dismiss_hotkey hotkeys_status').split()
    detach(s, [getattr(s, name) for name in names])
    detach(s, [voice.microphone, voice.refresh_button, voice.speak])
    # Only this settings workspace loses its redundant outer scroll wrapper.
    s.scroll.takeWidget()
    s.layout().replaceWidget(s.scroll, s.content)
    s.scroll.hide()
    s.content.show()
    s.body.setContentsMargins(16, 12, 16, 8)
    s.body.setSpacing(8)
    s.body.setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
    s.footer.layout().setContentsMargins(16, 6, 16, 6)
    clear_page(s.general_page)
    system = form('Общие', [('Запускать вместе с Windows', s.startup),
        ('Поверх других окон', s.on_top), ('Закрытие скрывает Eidos в трей', s.close_to_tray),
        ('Запускать в трее', s.start_in_tray), ('Язык интерфейса', s.language)])
    system.body.addWidget(s.startup_status)
    s.startup_status.show()
    appearance = form('Внешний вид', [('Тема приложения', s.theme), ('Акцентный цвет', s.accent_color),
        ('Анимации маскота', s.animation), ('Отключить анимации', s.reduce_animations)])
    character = form('Плавающий маскот', [('Показывать мини-персонажа', s.mascot_visible),
        ('Плавающий маскот', s.floating_enabled), ('Маскот поверх окон', s.floating_pinned)])
    character.body.addWidget(s.character_button)
    s.character_button.show()
    s.general_page.body.addWidget(ResponsiveRow([column(system), column(appearance, character)], threshold=650, spacing=8))
    s.general_page.body.addStretch()
    s.extra_settings_button.hide()
    s.extra_settings.hide()
    device_page = voice.config_tabs.widget(0)
    activation = voice.config_tabs.widget(1)
    clear_page(device_page)
    clear_page(activation)
    device = form('Микрофон и озвучка', [('Микрофон', row(voice.microphone, voice.refresh_button)),
        ('Озвучивать ответы', voice.speak), ('Краткие голосовые ответы', s.voice_response_brief),
        ('Глобальная клавиша голоса', s.voice_hotkey_enabled), ('Начать / остановить голос', s.voice_hotkey)])
    recognition = form('Распознавание', [('Движок распознавания', s.stt_engine),
        ('Локальная модель Vosk', s.vosk_model_path), ('', s.vosk_select),
        ('Модель', s.model), ('Вычисления', s.device),
        ('Чувствительность речи', s.voice_sensitivity), ('Лимит команды', s.voice_max_seconds)])
    speech = form('Озвучка', [('Провайдер озвучки', s.tts_provider), ('Голос', s.tts_voice),
        ('Голос Windows SAPI', s.sapi_voice), ('Характер общения', s.communication_style),
        ('Скорость относительно обычной', s.tts_rate), ('Громкость', s.tts_volume)])
    speech.body.addWidget(s.voices_button)
    speech.body.addWidget(row(s.sample_button, s.stop_speech_button))
    s.voices_button.show()
    device.body.addWidget(voice.details_button)
    device.body.addWidget(voice.journal)
    voice.details_button.show()
    device_page.body.addWidget(ResponsiveRow([column(device, recognition), column(speech)], threshold=650, spacing=8))
    device_page.body.addStretch()
    # Preserve SettingsPage._recognition_controls interface with row proxies.
    class FormRow:
        def __init__(self, card, control): self.card, self.control = card, control
        def setVisible(self, visible): self.card.form.setRowVisible(self.control, visible)
    s.vosk_row = FormRow(recognition, s.vosk_model_path)
    s.whisper_row = FormRow(recognition, s.model)
    def recognition_changed(*args):
        s._recognition_controls()
        vosk = s.stt_engine.currentData() == 'vosk'
        recognition.form.setRowVisible(s.vosk_select, vosk)
        recognition.form.setRowVisible(s.device, not vosk)  # Vosk uses CPU.
    s.stt_engine.currentIndexChanged.connect(recognition_changed)
    recognition_changed()
    def speech_changed(*args):
        sapi = s.tts_provider.currentData() == 'sapi'
        speech.form.setRowVisible(s.sapi_voice, sapi)
        speech.form.setRowVisible(s.tts_voice, not sapi)
        s.voices_button.setVisible(sapi)
    s.tts_provider.currentIndexChanged.connect(speech_changed)
    speech_changed()
    wake = form('Активация словом — Porcupine', [('Включить активацию словом', s.wake_word_enabled),
        ('Windows-модель Eidos (.ppn)', s.wake_keyword_path), ('Языковая модель (.pv)', s.wake_model_path),
        ('AccessKey', s.wake_access_key), ('Чувствительность ключевого слова', s.wake_sensitivity)])
    wake.body.addWidget(s.wake_secret_button)
    wake.body.addWidget(s.wake_status)
    s.wake_status.show()
    activation.body.addWidget(wake)
    activation.body.addStretch()
    translation = Page('Экран и перевод', 'Горячие клавиши перевода')
    clear_page(translation)
    keys = form('Горячие клавиши перевода', [('Включить горячие клавиши', s.hotkeys_enabled),
        ('Выделить текст и перевести', s.capture_hotkey), ('Обновить эту область', s.repeat_hotkey),
        ('Снять перевод', s.dismiss_hotkey)])
    keys.body.addWidget(s.hotkeys_status)
    s.hotkeys_status.show()
    translation.body.addWidget(keys)
    translation.body.addStretch()
    s.tabs.addTab(translation, 'Экран и перевод')
    # One application-settings save footer covers General, Voice and Translation.
    s.tabs.currentChanged.connect(lambda index: s.footer.setVisible(index not in (1, 2)))
    model_page = ui.sections['Модель']
    model_controls = [getattr(ui, name) for name in ('provider model_name ollama_url cloud_model gemini_model gemini_key context_size '
        'search_provider model_save server_start model_pull model_refresh model_status model_test hardware_test '
        'hardware_display apps_list app_add app_remove').split()]
    detach(ui, model_controls)
    clear_page(model_page)
    model = form('Модель', [('Провайдер', ui.provider), ('Ollama-модель', ui.model_name),
        ('Адрес', ui.ollama_url), ('Облачная модель', ui.cloud_model),
        ('Модель Gemini', ui.gemini_model), ('Gemini API Key', ui.gemini_key),
        ('Контекст Ollama, токенов', ui.context_size), ('Поисковик', ui.search_provider)])
    diagnostics = Card(margins=12)
    diagnostics.body.addWidget(ui.model_status)
    diagnostics.body.addWidget(row(ui.server_start, ui.model_pull))
    diagnostics.body.addWidget(ui.model_refresh)
    diagnostics.body.addWidget(row(ui.hardware_test, ui.model_test))
    ui.hardware_display.setMinimumHeight(80)
    ui.hardware_display.setMaximumHeight(120)
    diagnostics.body.addWidget(ui.hardware_display)
    for c in (ui.model_status, ui.model_refresh, ui.hardware_display): c.show()
    model_page.body.addWidget(ResponsiveRow([model, diagnostics], threshold=650, spacing=8))
    model_page.body.addWidget(ui.model_save)
    ui.model_save.show()
    model_page.body.addStretch()
    def model_changed(*args):
        local = ui.provider.currentData() == 'ollama'
        gemini = ui.provider.currentData() == 'gemini'
        model.form.setRowVisible(ui.cloud_model, ui.provider.currentData() == 'openai')
        for c in (ui.gemini_model, ui.gemini_key): model.form.setRowVisible(c, gemini)
        for c in (ui.model_name, ui.ollama_url, ui.context_size): model.form.setRowVisible(c, local)
        for c in (ui.server_start, ui.model_pull): c.setVisible(local)
        ui.hardware_test.setVisible(local)
        ui.model_refresh.setText('Проверить ключ' if gemini else 'Проверить состояние сервиса')
        ui.model_status.setText('Gemini · подключение не проверено. Запрос и выбранный контекст отправляются в Google.'
            if gemini else 'OpenAI · подключение не проверено.' if not local else 'Ollama · подключение не проверено.')
    ui.provider.currentIndexChanged.connect(model_changed)
    model_changed()
    # Application grants belong to Tools, while the same bound controls survive.
    window.tools.tabs.widget(0).body.addWidget(row(ui.apps_list, ui.app_add, ui.app_remove))
    connections = ui.sections['Подключения']
    cards = [connections.body.itemAt(i).widget() for i in range(connections.body.count())
             if isinstance(connections.body.itemAt(i).widget(), Card)]
    clear_page(connections)
    for card in cards:
        card.body.setContentsMargins(12, 10, 12, 10)
        card.body.setSpacing(6)
        for note in card.findChildren(QLabel):
            if note.objectName() == 'h2': note.setWordWrap(True)
            if note.objectName() == 'muted':
                card.setToolTip(note.source_text())
                note.hide()
        card.show()
    for kind in ('telegram', 'discord'):
        ui.bot_enabled[kind].setToolTip(ui.bot_enabled[kind].source_text())
        ui.bot_enabled[kind].setText('Включить бота')
        ui.bot_users[kind].setToolTip(ui.bot_users[kind].placeholderText())
        ui.bot_channels[kind].setToolTip(ui.bot_channels[kind].placeholderText())
    # Original construction order: Telegram, Discord, OpenAI, Brave, permissions.
    connections.body.addWidget(ResponsiveRow([cards[3], cards[2]], threshold=650, spacing=8))
    connections.body.addWidget(ResponsiveRow([cards[0], cards[1], cards[4]], threshold=750, spacing=8))
    connections.body.addWidget(ResponsiveRow([ui.connections_save, ui.secret_delete, ui.secret_delete_button], threshold=550, spacing=6))
    for control in (ui.connections_save, ui.secret_delete, ui.secret_delete_button): control.show()
    connections.body.addStretch()
    for card in (system, appearance, character, device, recognition, speech, model, *cards):
        card.body.addStretch()
    # Compact only this workspace; keep main/voice widgets' global geometry.
    s.setStyleSheet('QWidget { font-size: 12px; } QLabel#h1 { font-size: 24px; } '
        'QLabel#h2 { font-size: 16px; } QPushButton { padding: 5px 9px; min-height: 18px; } '
        'QComboBox { padding: 5px 24px 5px 8px; min-height: 18px; } '
        'QLineEdit, QSpinBox, QDoubleSpinBox { padding: 5px; }')
    for control in (s.vosk_model_path, s.wake_keyword_path, s.wake_model_path):
        control.setToolTip(control.placeholderText() or control.accessibleName())
