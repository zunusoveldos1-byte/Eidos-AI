from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QKeySequenceEdit
from eidos.ui.localized import QWidget, QSpinBox, QDoubleSpinBox, QLineEdit
from eidos.core.config import AppConfig, MODELS
from ..components import Card, Page, ResponsiveRow, Toggle, button, combo, label, setting_row


class SettingsPage(Page):
    save_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    sample_requested = pyqtSignal()
    stop_speech_requested = pyqtSignal()
    wake_secret_requested = pyqtSignal(str)
    voices_requested = pyqtSignal()
    onboarding_requested = pyqtSignal()
    profile_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__('Настройки', 'Настройте Eidos под себя')
        outer_body = self.body
        self.general_page = Page('Общие параметры', 'Запуск, внешний вид и дополнительные параметры')
        self.body = self.general_page.body
        general = Card()
        general.heading('Общие', 'settings')
        self.startup = Toggle('Запускать вместе с Windows')
        general.body.addWidget(setting_row('Запускать вместе с Windows', self.startup))
        self.startup_status = label('', 'muted')
        general.body.addWidget(self.startup_status)
        self.on_top = Toggle('Поверх других окон')
        general.body.addWidget(setting_row('Поверх других окон', self.on_top))
        self.language = combo()
        for code, title in [('ru', 'Русский'), ('en', 'English'), ('ky', 'кыргызча'), ('uz', 'o‘zbekcha'), ('kk', 'қазақша')]:
            self.language.addRawItem(title, code)
        general.body.addWidget(setting_row('Язык интерфейса', self.language))
        self.profile = combo()
        self.profile.setEditable(True)
        self.profile_row = setting_row('Текущий профиль', self.profile)
        general.body.addWidget(self.profile_row)
        self.profile_button = button('Сменить / создать профиль')
        self.profile_button.clicked.connect(lambda: self.profile_requested.emit(self.profile.currentText().strip()))
        self.profile_buttons = QWidget()
        profile_buttons_layout = QVBoxLayout(self.profile_buttons)
        profile_buttons_layout.addWidget(self.profile_button)
        general.body.addWidget(self.profile_buttons)
        self.onboarding_button = button('Заполнить опрос снова')
        self.onboarding_button.clicked.connect(self.onboarding_requested)
        profile_buttons_layout.addWidget(self.onboarding_button)
        self.mascot_visible = Toggle('Показывать мини-персонажа')
        general.body.addWidget(setting_row('Показывать мини-персонажа', self.mascot_visible))
        self.character_button = button('Показать персонажа', 'user')
        general.body.addWidget(self.character_button)
        self.processing_info = label('Обработка: OCR и Whisper — локально. Озвучка Edge и перевод Google отправляют только текст. SAPI работает локально.', 'muted')
        general.body.addWidget(self.processing_info)
        voice = self.voice_card = Card()
        voice.heading('Голос', 'mic')
        self.microphone = combo()
        self.microphone.setAccessibleName('Микрофон в настройках')
        self.microphone_row = setting_row('Микрофон', self.microphone)
        voice.body.addWidget(self.microphone_row)
        self.speak = Toggle('Озвучивать ответы')
        self.speak_row = setting_row('Озвучивать ответы', self.speak)
        voice.body.addWidget(self.speak_row)
        self.tts_voice = combo()
        self.tts_voice.addItem('Светлана', 'ru-RU-SvetlanaNeural')
        self.tts_voice.addItem('Дмитрий', 'ru-RU-DmitryNeural')
        voice.body.addWidget(setting_row('Голос', self.tts_voice))
        self.communication_style = combo()
        for title, value in [('Нейтральный', 'neutral'), ('Дружелюбный', 'friendly'), ('Энергичный', 'energetic')]:
            self.communication_style.addItem(title, value)
        voice.body.addWidget(setting_row('Характер общения', self.communication_style))
        voice.body.addWidget(label('Характер меняет реплики и темп. Edge / SAPI не предоставляют эмоциональные стили.', 'muted'))
        self.body.addWidget(ResponsiveRow([general, voice], threshold=690))
        background = Card()
        background.heading('Голос в фоне', 'mic')
        self.close_to_tray = Toggle('Закрытие скрывает Eidos в трей')
        self.start_in_tray = Toggle('Запускать в трее')
        self.floating_enabled = Toggle('Плавающий маскот')
        self.floating_pinned = Toggle('Маскот поверх окон')
        self.reduce_animations = Toggle('Отключить анимации')
        self.reduce_animations.setToolTip('Отключает декоративное движение, появление и переход меню. Также учитываются настройки анимации Windows.')
        self.voice_hotkey_enabled = Toggle('Глобальная клавиша голоса')
        self.voice_hotkey = self._shortcut_editor('Начать / остановить голосовой ввод')
        for text, control in [('Закрытие скрывает Eidos в трей', self.close_to_tray),
                              ('Запускать в трее', self.start_in_tray),
                              ('Плавающий маскот', self.floating_enabled), ('Маскот поверх окон', self.floating_pinned),
                              ('Отключить анимации', self.reduce_animations),
                              ('Глобальная клавиша голоса', self.voice_hotkey_enabled), ('Начать / остановить голос', self.voice_hotkey)]:
            background.body.addWidget(setting_row(text, control))
        speech = self.speech_card = Card()
        speech.heading('Озвучка', 'mic')
        self.tts_provider = combo()
        self.tts_provider.addItem('Edge — онлайн', 'edge')
        self.tts_provider.addItem('Windows SAPI — локально', 'sapi')
        self.sapi_voice = combo()
        self.sapi_voice.setEditable(True)
        self.sapi_voice.addItem('Русский голос Windows по умолчанию', '')
        self.tts_rate, self.tts_volume = QSpinBox(), QSpinBox()
        self.tts_rate.setRange(-50, 100)
        self.tts_rate.setSuffix(' %')
        self.tts_volume.setRange(0, 100)
        self.tts_volume.setSuffix(' %')
        self.voice_response_brief = Toggle('Краткие голосовые ответы')
        for text, control in [('Провайдер озвучки', self.tts_provider), ('Голос Windows SAPI', self.sapi_voice),
                              ('Скорость относительно обычной', self.tts_rate), ('Громкость', self.tts_volume),
                              ('Краткие голосовые ответы', self.voice_response_brief)]:
            speech.body.addWidget(setting_row(text, control))
        self.sample_button = button('Прослушать пример', 'mic')
        self.voices_button = button('Найти голоса Windows')
        self.voices_button.clicked.connect(self.voices_requested)
        speech.body.addWidget(self.voices_button)
        self.stop_speech_button = button('Остановить озвучку')
        self.sample_button.clicked.connect(self.sample_requested)
        self.stop_speech_button.clicked.connect(self.stop_speech_requested)
        speech.body.addWidget(ResponsiveRow([self.sample_button, self.stop_speech_button], threshold=500))
        wake = self.wake_card = Card()
        wake.heading('Активация словом — Porcupine', 'mic')
        self.wake_word_enabled = Toggle('Локально ждать слово Eidos')
        self.wake_keyword_path, self.wake_model_path, self.wake_access_key = QLineEdit(), QLineEdit(), QLineEdit()
        self.wake_access_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.wake_access_key.setPlaceholderText('Новый AccessKey; хранится только в Windows Credential Manager')
        for text, control in [('Включить активацию словом', self.wake_word_enabled), ('Windows-модель Eidos (.ppn)', self.wake_keyword_path),
                              ('Языковая модель (.pv)', self.wake_model_path), ('AccessKey', self.wake_access_key)]:
            wake.body.addWidget(setting_row(text, control))
        self.wake_sensitivity = QDoubleSpinBox()
        self.wake_sensitivity.setRange(0., 1.)
        self.wake_sensitivity.setSingleStep(.05)
        wake.body.addWidget(setting_row('Чувствительность ключевого слова', self.wake_sensitivity))
        self.wake_secret_button = button('Сохранить ключ отдельно')
        self.wake_secret_button.clicked.connect(lambda: self.wake_secret_requested.emit(self.wake_access_key.text()))
        wake.body.addWidget(self.wake_secret_button)
        self.wake_status = label('Без ключа и модели голос по кнопке остаётся доступен.', 'muted')
        self.wake_status.setWordWrap(True)
        wake.body.addWidget(self.wake_status)
        wake.body.addWidget(label('Обнаружение слова локальное. Во время озвучки микрофон освобождается. Нужен optional пакет pvporcupine и ваши модели.', 'muted'))
        self.body.addWidget(background)
        # MainWindow places this card in the dedicated activation tab.
        shortcuts = Card()
        shortcuts.heading('Горячие клавиши перевода', 'languages')
        self.hotkeys_enabled = Toggle('Включить горячие клавиши перевода')
        shortcuts.body.addWidget(setting_row('Включить горячие клавиши', self.hotkeys_enabled))
        self.capture_hotkey = self._shortcut_editor('Выбрать область и перевести')
        self.repeat_hotkey = self._shortcut_editor('Обновить снимок выбранной области')
        self.dismiss_hotkey = self._shortcut_editor('Снять перевод с экрана')
        shortcuts.body.addWidget(setting_row('Выделить текст и перевести', self.capture_hotkey))
        shortcuts.body.addWidget(setting_row('Обновить эту область', self.repeat_hotkey))
        shortcuts.body.addWidget(setting_row('Снять перевод', self.dismiss_hotkey))
        shortcuts.body.addWidget(label('Нажмите на поле и введите свою комбинацию. Крестик отключает отдельное действие. Изменения применяются кнопкой «Сохранить».', 'muted'))
        self.hotkeys_status = label('', 'muted')
        shortcuts.body.addWidget(self.hotkeys_status)
        self.extra_settings_button = button('Дополнительные параметры и клавиши', 'settings')
        self.extra_settings_button.setCheckable(True)
        self.body.addWidget(self.extra_settings_button)
        self.extra_settings = QWidget()
        self.extra_settings_layout = QVBoxLayout(self.extra_settings)
        self.extra_settings_layout.addWidget(shortcuts)
        self.extra_settings.hide()
        self.extra_settings_button.toggled.connect(self.extra_settings.setVisible)
        self.body.addWidget(self.extra_settings)
        recognition = Card()
        recognition.heading('Распознавание', 'wave')
        self.stt_engine = combo()
        self.stt_engine.addItem('Faster-Whisper', 'whisper')
        self.stt_engine.addItem('Vosk — потоковый локальный', 'vosk')
        recognition.body.addWidget(setting_row('Движок распознавания', self.stt_engine))
        self.vosk_model_path = QLineEdit()
        self.vosk_model_path.setPlaceholderText('Каталог распакованной модели Vosk')
        self.vosk_row = setting_row('Локальная модель Vosk', self.vosk_model_path)
        recognition.body.addWidget(self.vosk_row)
        self.vosk_select = button('Выбрать папку')
        recognition.body.addWidget(self.vosk_select)
        self.vosk_select.clicked.connect(self._choose_vosk_model)
        self.model = combo()
        self.model.addItems(MODELS)
        self.whisper_row = setting_row('Модель', self.model)
        recognition.body.addWidget(self.whisper_row)
        self.stt_engine.currentIndexChanged.connect(self._recognition_controls)
        self._recognition_controls()
        recognition.body.addWidget(label('Модели загружаются только из локальных файлов. Подготовьте модель перед запуском; автоматического скачивания нет.', 'muted'))
        self.voice_sensitivity = QDoubleSpinBox()
        self.voice_sensitivity.setRange(0., 1.)
        self.voice_sensitivity.setSingleStep(.05)
        self.voice_max_seconds = QSpinBox()
        self.voice_max_seconds.setRange(5, 120)
        self.voice_max_seconds.setSuffix(' с')
        recognition.body.addWidget(setting_row('Чувствительность речи', self.voice_sensitivity))
        recognition.body.addWidget(setting_row('Лимит команды', self.voice_max_seconds))
        recognition.body.addWidget(label('Лёгкая обработка шума и VAD. В сильном шуме подойдите ближе к микрофону.', 'muted'))
        self.advanced_button = button('Дополнительные параметры', 'arrow')
        self.advanced_button.setCheckable(True)
        recognition.body.addWidget(self.advanced_button)
        self.advanced = QWidget()
        advanced_layout = QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.device = combo()
        self.device.addItem('CPU / int8', 'cpu')
        self.device.addItem('CUDA / float16', 'cuda')
        advanced_layout.addWidget(setting_row('Вычисления', self.device))
        advanced_layout.addWidget(label('CUDA требует совместимых NVIDIA, cuBLAS и cuDNN.', 'muted'))
        self.advanced.hide()
        self.advanced_button.toggled.connect(self.advanced.setVisible)
        recognition.body.addWidget(self.advanced)
        appearance = Card()
        appearance.heading('Внешний вид', 'monitor')
        self.theme = combo()
        self.theme.addItem('Тёмная', 'dark')
        self.theme.addItem('Светлая', 'light')
        appearance.body.addWidget(setting_row('Тема приложения', self.theme))
        self.accent_color = combo()
        for title, color in [('Изумрудный', '#25E6A1'), ('Синий', '#458BEA'), ('Фиолетовый', '#AB7DEA'), ('Янтарный', '#E4BC76')]:
            self.accent_color.addItem(title, color)
        appearance.body.addWidget(setting_row('Акцентный цвет', self.accent_color))
        self.animation = Toggle('Анимации маскота')
        appearance.body.addWidget(setting_row('Анимации маскота', self.animation))
        appearance.body.addWidget(label('Спокойная короткая анимация при смене состояния', 'muted'))
        self.extra_settings_layout.addWidget(recognition)
        self.body.addWidget(appearance)
        self.feedback = label('', 'secondary')
        self.body.addWidget(self.feedback)
        self.body.addStretch()
        self.body = outer_body
        footer = QWidget()
        footer.setStyleSheet('border-top: 1px solid #29362F;')
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(28, 18, 28, 18)
        footer_layout.addWidget(label('Некоторые параметры доступны после подключения модулей', 'muted'), 1)
        self.reset_button = button('Сбросить')
        self.reset_button.clicked.connect(self.reset_requested)
        self.save_button = button('Сохранить', primary=True)
        self.save_button.clicked.connect(self.save_requested)
        footer_layout.addWidget(self.reset_button)
        footer_layout.addWidget(self.save_button)
        self.layout().addWidget(footer)
        self.footer = footer

    def _recognition_controls(self, *args):
        vosk = self.stt_engine.currentData() == 'vosk'
        self.vosk_row.setVisible(vosk)
        self.vosk_select.setVisible(vosk)
        self.whisper_row.setVisible(not vosk)

    def _choose_vosk_model(self):
        from eidos.ui.localized import QFileDialog
        path = QFileDialog.getExistingDirectory(self, 'Локальная модель Vosk', self.vosk_model_path.text())
        if path:
            self.vosk_model_path.setText(path)

    def load(self, config: AppConfig) -> None:
        self.startup.setChecked(config.startup_enabled)
        self.language.setCurrentIndex(self.language.findData(config.ui_language))
        self.theme.setCurrentIndex(self.theme.findData(config.theme))
        if self.accent_color.findData(config.accent_color) < 0:
            self.accent_color.addItem(config.accent_color, config.accent_color)
        self.accent_color.setCurrentIndex(self.accent_color.findData(config.accent_color))
        self.mascot_visible.setChecked(not config.mascot_hidden)
        self.stt_engine.setCurrentIndex(self.stt_engine.findData(config.stt_engine))
        from pathlib import Path
        prepared = Path(__file__).resolve().parents[3] / '.cache/voice-models/vosk-model-small-ru-0.22'
        self.vosk_model_path.setText(config.vosk_model_path or (str(prepared) if (prepared / 'am/final.mdl').is_file() else ''))
        self.communication_style.setCurrentIndex(self.communication_style.findData(config.communication_style))
        self.voice_sensitivity.setValue(config.voice_sensitivity)
        self.wake_sensitivity.setValue(config.wake_sensitivity)
        self.voice_max_seconds.setValue(config.voice_max_seconds)
        for name in ('close_to_tray', 'start_in_tray', 'floating_enabled', 'floating_pinned', 'reduce_animations',
                     'voice_hotkey_enabled', 'voice_response_brief', 'wake_word_enabled'):
            getattr(self, name).setChecked(getattr(config, name))
        self.voice_hotkey.setKeySequence(QKeySequence(config.voice_hotkey))
        self.tts_provider.setCurrentIndex(self.tts_provider.findData(config.tts_provider))
        self.tts_rate.setValue(config.tts_rate)
        self.tts_volume.setValue(config.tts_volume)
        index = self.sapi_voice.findData(config.sapi_voice)
        if index < 0:
            self.sapi_voice.addItem(config.sapi_voice, config.sapi_voice)
            index = self.sapi_voice.count() - 1
        self.sapi_voice.setCurrentIndex(index)
        self.wake_keyword_path.setText(config.wake_keyword_path)
        self.wake_model_path.setText(config.wake_model_path)
        self.hotkeys_enabled.setChecked(config.translation_hotkeys_enabled)
        for control, text in [(self.capture_hotkey, config.translation_capture_hotkey),
                              (self.repeat_hotkey, config.translation_repeat_hotkey),
                              (self.dismiss_hotkey, config.translation_dismiss_hotkey)]:
            control.setKeySequence(QKeySequence.fromString(text, QKeySequence.SequenceFormat.PortableText))
        self.model.setCurrentText(config.whisper_model)
        self.device.setCurrentIndex(self.device.findData(config.device))
        self.speak.setChecked(config.speak)
        self.on_top.setChecked(config.always_on_top)
        self.animation.setChecked(config.mascot_animation)
        index = self.tts_voice.findData(config.tts_voice)
        if index < 0:
            self.tts_voice.addItem(config.tts_voice, config.tts_voice)
            index = self.tts_voice.count() - 1
        self.tts_voice.setCurrentIndex(index)
        self.feedback.setText('')

    def background_values(self):
        values = {name: getattr(self, name).isChecked() for name in
                  ('close_to_tray', 'start_in_tray', 'floating_enabled', 'floating_pinned', 'reduce_animations',
                   'voice_hotkey_enabled', 'voice_response_brief', 'wake_word_enabled')}
        values.update(voice_hotkey=self.voice_hotkey.keySequence().toString(QKeySequence.SequenceFormat.PortableText),
                      startup_enabled=self.startup.isChecked(), ui_language=self.language.currentData(),
                      theme=self.theme.currentData(), accent_color=self.accent_color.currentData(),
                      mascot_hidden=not self.mascot_visible.isChecked(), stt_engine=self.stt_engine.currentData(),
                      vosk_model_path=self.vosk_model_path.text().strip(),
                      communication_style=self.communication_style.currentData(),
                      voice_sensitivity=self.voice_sensitivity.value(), voice_max_seconds=self.voice_max_seconds.value(),
                      wake_sensitivity=self.wake_sensitivity.value(),
                      tts_provider=self.tts_provider.currentData(), tts_rate=self.tts_rate.value(),
                      tts_volume=self.tts_volume.value(), sapi_voice=(self.sapi_voice.currentData() or '')
                      if self.sapi_voice.currentIndex() >= 0 and self.sapi_voice.currentText() == self.sapi_voice.itemText(self.sapi_voice.currentIndex())
                      else self.sapi_voice.currentText().strip(),
                      wake_keyword_path=self.wake_keyword_path.text().strip(), wake_model_path=self.wake_model_path.text().strip())
        return values

    def load_sapi_voices(self, voices):
        selected = self.background_values()['sapi_voice']
        self.sapi_voice.clear()
        self.sapi_voice.addItem('Русский голос Windows по умолчанию', '')
        for identifier, description in voices:
            self.sapi_voice.addRawItem(description, identifier)
        index = self.sapi_voice.findData(selected)
        if index >= 0:
            self.sapi_voice.setCurrentIndex(index)
        else:
            self.sapi_voice.setEditText(selected)
        self.feedback.setText(f'Найдено голосов Windows: {len(voices)}.')

    @staticmethod
    def _shortcut_editor(name):
        control = QKeySequenceEdit()
        control.setMaximumSequenceLength(1)
        control.setClearButtonEnabled(True)
        control.setAccessibleName(name)
        control.setMinimumWidth(180)
        control.setStyleSheet('QKeySequenceEdit QLineEdit { background: #151E18; color: #F2F6F3; border: 1px solid #35453C; border-radius: 8px; padding: 10px; } QKeySequenceEdit QLineEdit:focus { border: 2px solid #2FE09B; }')
        return control
