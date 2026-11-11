from PyQt6.QtCore import Qt, QTimer, QRect, QThread, QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QProgressBar
from eidos.ui.localized import QWidget, QPlainTextEdit
from PyQt6.QtGui import QCursor
from types import SimpleNamespace
from eidos.modules.ocr.engine import WindowsOCR, TextLine
from eidos.modules.ocr.multilingual import LANGUAGES
from ..screen_translation import RegionSelector, TranslationWorker, TextTranslationWorker, TranslationOverlay, OverlayControls
from ..components import Card, Page, ResponsiveRow, Toggle, button, combo, label, setting_row


class TranslationPage(Page):
    stopped = pyqtSignal()
    preferences_changed = pyqtSignal(str, str, bool)
    capture_started = pyqtSignal()
    capture_finished = pyqtSignal()
    speak_requested = pyqtSignal(str)
    explain_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__('Экран и перевод', '')
        self.worker = None
        self.captured_image = None
        self.region = None
        self.last_lines = []
        self.selectors = []
        self.overlay = self.overlay_controls = None
        self.closing = self._selecting = self._refreshing = self._cancelled = False
        self._updating_text = self._busy_state = False
        self._capture_backup = None
        self._capture_window_visible = False
        self._ocr_only = False
        self.status = label('●  Готов к выделению', 'moduleBadge')
        self.header.addWidget(self.status)
        source, target = Card(margins=12), Card(margins=12)
        for card, title in [(source, 'Язык исходного текста'), (target, 'Перевести на')]:
            card.body.setSpacing(4)
            card.body.addWidget(label(title, 'muted'))
        self.source, self.target = combo(), combo()
        self.source.addItem('Автоопределение', 'auto')
        for code, _, title in LANGUAGES:
            self.source.addItem(title, code)
            self.target.addItem(title, code)
        source.body.addWidget(self.source)
        target.body.addWidget(self.target)
        self.source.setToolTip('Для коротких надписей явный выбор языка может быть точнее автоопределения')
        self.select_button = button('Выделить текст на экране', 'scan', True)
        self.select_button.setMinimumHeight(46)
        self.select_button.clicked.connect(self.start_capture)
        self.body.addWidget(ResponsiveRow([source, target, self.select_button], threshold=660))
        self.hotkey_hint = label('Горячие клавиши можно изменить в настройках.', 'muted')
        self.body.addWidget(self.hotkey_hint)
        self.show_overlay = Toggle('Показывать перевод поверх исходного текста')
        self.show_overlay.setChecked(True)
        self.body.addWidget(setting_row('Показывать перевод поверх исходного текста', self.show_overlay))
        self.feedback = label('Текст отправляется Google только после запуска перевода. Языки и способ показа запоминаются.', 'muted')
        self.body.addWidget(self.feedback)
        self.provider = combo()
        self.provider.addItem('Google — отправляется только распознанный текст', 'google')
        self.provider.addItem('Не отправлять текст в сеть', '')
        self.body.addWidget(setting_row('Провайдер перевода', self.provider))
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.region_info = label('Область ещё не выбрана. Начните с зелёной кнопки или вставьте текст ниже.', 'muted')
        self.body.addWidget(self.region_info)
        self.loading_widget = QWidget()
        loading_row = QHBoxLayout(self.loading_widget)
        loading_row.setContentsMargins(0, 0, 0, 0)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedSize(130, 8)
        self.loading_bar.setStyleSheet('QProgressBar { border: none; background: #29362F; border-radius: 4px; } QProgressBar::chunk { background: #2FE09B; border-radius: 4px; }')
        self.loading_text = label('Распознавание…', 'muted')
        loading_row.addWidget(self.loading_bar)
        loading_row.addWidget(self.loading_text, 1)
        self.loading_widget.hide()
        self.body.addWidget(self.loading_widget)
        self.refresh_button = button('Обновить эту область', 'refresh')
        self.refresh_button.setToolTip('Сделать новый снимок в том же месте — например, после прокрутки')
        self.refresh_button.clicked.connect(self.refresh_capture)
        self.remove_button = button('Убрать перевод с экрана')
        self.remove_button.clicked.connect(self.dismiss_overlay)
        self.cancel_button = button('Отменить обработку')
        self.cancel_button.clicked.connect(self.cancel_translation)
        self.cancel_button.hide()
        self.recognize_button = button('Распознать текст', 'scan')
        self.recognize_button.clicked.connect(self.recognize_capture)
        self.body.addWidget(ResponsiveRow([self.recognize_button, self.refresh_button, self.remove_button, self.cancel_button], threshold=520))
        # Text buffers retain service/voice compatibility without editor cards.
        self.storage = QWidget(self)
        self.storage.hide()
        self.original = SimpleNamespace(text=QPlainTextEdit(self.storage))
        self.translated = SimpleNamespace(text=QPlainTextEdit(self.storage))
        self.translated.copy = lambda: QApplication.clipboard().setText(self.translated.text.toPlainText())
        self.original.text.setReadOnly(False)
        self.original.text.setMinimumHeight(150)
        self.translated.text.setMinimumHeight(150)
        self.paste_button = button('Вставить текст', 'file')
        self.paste_button.clicked.connect(self.paste_text)
        self.retry_button = button('Перевести текст', 'languages', True)
        self.retry_button.setToolTip('Перевести содержимое левой карточки, включая ваши исправления')
        self.retry_button.clicked.connect(self.retry_translation)
        self.copy_translation = button('Скопировать перевод', 'copy')
        self.copy_translation.clicked.connect(self.translated.copy)
        self.speak_button = button('Озвучить перевод', 'mic')
        self.speak_button.clicked.connect(lambda: self.speak_requested.emit(self.translated.text.toPlainText()))
        self.speak_button.setParent(self)
        self.speak_button.hide()
        self.explain_button = button('Объяснить выбранный текст', 'message')
        self.explain_button.setToolTip('Отправить только текст этой области выбранной модели')
        self.explain_button.clicked.connect(lambda: self.explain_requested.emit(self.original.text.toPlainText().strip()))
        self.explain_button.setParent(self)
        self.explain_button.hide()
        self.translated.text.textChanged.connect(self._update_actions)
        self.original.text.textChanged.connect(self._text_changed)
        # Remove legacy action rows from the visible layout. Their bound service
        # entry points remain internal; there is no manual editor UI.
        while self.body.count() > 1:
            item = self.body.takeAt(1)
            if item.widget():
                item.widget().setParent(self.storage)
                item.widget().hide()
        for control in (self.select_button, self.source, self.target, self.provider,
                        self.show_overlay, self.feedback, self.loading_widget):
            control.setParent(self.content)
        for control in (self.paste_button, self.retry_button, self.copy_translation,
                        self.recognize_button, self.refresh_button, self.remove_button,
                        self.cancel_button):
            control.setParent(self.storage)
            control.hide()
        languages = ResponsiveRow([setting_row('Язык исходного текста', self.source),
                                   setting_row('Перевести на', self.target)], threshold=650)
        self.body.addWidget(languages)
        self.body.addWidget(setting_row('Провайдер перевода', self.provider))
        self.body.addWidget(setting_row('Показывать перевод поверх исходного текста', self.show_overlay))
        self.body.addWidget(self.select_button)
        for control in (self.source, self.target, self.provider, self.show_overlay, self.select_button): control.show()
        self.select_button.setToolTip('Отправляется только распознанный текст, не снимок. Перед отправкой проверяются секреты.')
        self.body.addStretch()
        self.instruction = label('Для перевода выделите область с помощью Ctrl+Alt+T или кнопки. Перевод отобразится прямо поверх текста.', 'secondary', centered=True)
        self.body.addWidget(self.instruction)
        self.body.addWidget(self.loading_widget)
        self.body.addWidget(self.feedback)
        self.feedback.setText('')
        self.feedback.hide()
        self.status.hide()
        self.body.addStretch()
        self.source.currentIndexChanged.connect(self._preferences_changed)
        self.target.currentIndexChanged.connect(self._preferences_changed)
        self.show_overlay.toggled.connect(self._preferences_changed)
        self._update_actions()
        self._status('Готов к выделению')

    def load_preferences(self, config):
        blockers = [QSignalBlocker(control) for control in (self.source, self.target, self.show_overlay)]
        self.source.setCurrentIndex(max(0, self.source.findData(config.translation_source_language)))
        self.target.setCurrentIndex(max(0, self.target.findData(config.translation_target_language)))
        self.show_overlay.setChecked(config.translation_show_overlay)
        blocker = QSignalBlocker(self.provider)
        self.provider.setCurrentIndex(max(0, self.provider.findData(config.translation_provider)))
        del blocker
        del blockers

    def _provider_changed(self):
        from dataclasses import replace
        window = self.window()
        if hasattr(window, '_persist'):
            if not window._persist(replace(window.config, translation_provider=self.provider.currentData())):
                self.load_preferences(window.config)

    def _preferences_changed(self, *args):
        if not self.show_overlay.isChecked():
            self.dismiss_overlay(restore=False)
        self.preferences_changed.emit(self.source.currentData(), self.target.currentData(), self.show_overlay.isChecked())

    def _status(self, text, kind='ready'):
        self.status.setText('●  ' + text)
        color = {'ready': '#2FE09B', 'busy': '#E4BC76', 'error': '#F08F8F'}[kind]
        self.status.setStyleSheet(f'color: {color}; background: #19251F; border: 1px solid {color}; border-radius: 13px; padding: 7px 11px; font-size: 12px;')

    @property
    def is_running(self):
        return self.worker is not None

    def _update_actions(self):
        busy = self._busy_state
        self.refresh_button.setEnabled(not busy and self.region is not None)
        self.recognize_button.setEnabled(not busy and not self._selecting)
        self.retry_button.setEnabled(not busy and (bool(self.original.text.toPlainText().strip()) or self.captured_image is not None))
        self.remove_button.setEnabled(self.overlay is not None)
        self.paste_button.setEnabled(not busy)
        self.copy_translation.setEnabled(bool(self.translated.text.toPlainText()))

    def _busy(self, value):
        self._busy_state = value
        for control in (self.select_button, self.source, self.target, self.provider, self.show_overlay):
            control.setEnabled(not value)
        self.original.text.setReadOnly(value)
        self._update_actions()
        self._set_loading(value, 'Подготовка перевода…')

    def _set_loading(self, busy, message):
        self.loading_text.setText(message)
        self.loading_widget.setVisible(busy)

    def _set_source_text(self, text):
        self._updating_text = True
        self.original.text.setPlainText(text)
        self._updating_text = False
        self._update_actions()

    def _text_changed(self):
        self._update_actions()
        if not self._updating_text:
            self.dismiss_overlay(restore=False)
            self.translated.text.clear()
            self._status('Текст изменён', 'busy')
            self.feedback.setText('Нажмите «Перевести текст», чтобы перевести исправления. Сам ввод текста ничего не отправляет.')

    def paste_text(self):
        if self.is_running or self._selecting:
            return
        text = QApplication.clipboard().text()
        if not text.strip():
            self.feedback.setText('В буфере обмена нет текста. Скопируйте его и нажмите «Вставить текст».')
            return
        self.last_lines = []
        self.original.text.setPlainText(text)
        self.original.text.setFocus()

    def start_capture(self, checked=False, *, local_only=False):
        if self.is_running or self._selecting or self.closing:
            return
        self._ocr_only = local_only
        self._cancelled = False
        self._hide_capture_overlays()
        self.capture_started.emit()
        self._selecting = True
        self._busy(True)
        self._status('Выделите текст мышью', 'busy')
        self._hide_window_for_capture()
        QTimer.singleShot(60, self._show_selectors)

    def _show_selectors(self):
        if self.closing or not self._selecting or self._refreshing:
            return
        try:
            snapshots = [(screen, screen.grabWindow(0)) for screen in QApplication.screens()]
            if not snapshots or any(snapshot.isNull() for _, snapshot in snapshots):
                raise RuntimeError('Не удалось захватить экран.')
            for screen, snapshot in snapshots:
                selector = RegionSelector(screen, snapshot)
                selector.selected.connect(self._selected)
                selector.cancelled.connect(self._cancel_selection)
                selector.entered.connect(self._selector_entered)
                self.selectors.append(selector)
            active = QApplication.screenAt(QCursor.pos()) or snapshots[0][0]
            chosen = next((s for s in self.selectors if s.screen is active), self.selectors[0])
            self._selector_entered(chosen)
            for selector in self.selectors:
                selector.show()
            chosen.activateWindow()
            chosen.setFocus()
        except Exception as exc:
            self._cancel_selection()
            self.feedback.setText(str(exc))

    def _selector_entered(self, active):
        for selector in self.selectors:
            selector.glow_enabled = selector is active
            if selector.glow_enabled: selector.pulse_timer.start()
            else: selector.pulse_timer.stop()
            selector.update()

    def _clear_selectors(self):
        self._selecting = self._refreshing = False
        for selector in self.selectors:
            selector.close()
            selector.deleteLater()
        self.selectors.clear()
        self._restore_capture_window()
        self.capture_finished.emit()

    def _hide_window_for_capture(self):
        self._capture_window_visible = self.window().isVisible()
        if self._capture_window_visible:
            self.window().hide()

    def _restore_capture_window(self):
        visible, self._capture_window_visible = self._capture_window_visible, False
        if visible and not self.closing:
            window = self.window()
            previous = window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
            window.show()
            window.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, previous)

    def _restore_window(self):
        if not self.closing:
            if self.window().isMinimized():
                self.window().setWindowState(self.window().windowState() & ~Qt.WindowState.WindowMinimized)
            self.window().show()
            self.window().raise_()
            self.window().activateWindow()

    def _cancel_selection(self):
        self._clear_selectors()
        self._busy(False)
        self._status('Выделение отменено')
        self._restore_capture_overlays()

    def _hide_capture_overlays(self):
        self._capture_backup = (self.region, self.captured_image, self.last_lines,
                                getattr(self, 'selected_screen', None), self.window().isVisible(),
                                bool(self.overlay and self.overlay.isVisible()),
                                bool(self.overlay_controls and self.overlay_controls.isVisible()))
        for widget in (self.overlay, self.overlay_controls):
            if widget:
                widget.hide()

    def _restore_capture_overlays(self):
        backup, self._capture_backup = self._capture_backup, None
        if backup is None:
            return False
        self.region, self.captured_image, self.last_lines, self.selected_screen, visible, layer, controls = backup
        if self.closing:
            return False
        if layer and self.overlay:
            self.overlay.show()
        if controls and self.overlay_controls:
            self.overlay_controls.show()
        return True

    def _selected(self, selector, rect):
        self.selected_screen = selector.screen
        self.region = QRect(rect)
        self.region.translate(selector.screen.geometry().topLeft())
        snapshot = selector.snapshot.toImage()
        self.captured_image = self._crop_image(snapshot, rect, selector.size())
        # Committing a new selection replaces the previous capture. A network
        # failure must keep these new coordinates available for retry.
        self._capture_backup = None
        self._clear_selectors()
        self.region_info.setText(f'Выбрана область {self.region.width()} × {self.region.height()}. Можно обновлять её снимок без нового выделения.')
        self._process_capture()

    @staticmethod
    def _crop_image(image, rect, logical_size):
        sx, sy = image.width() / logical_size.width(), image.height() / logical_size.height()
        pixels = QRect(round(rect.x() * sx), round(rect.y() * sy), round(rect.width() * sx), round(rect.height() * sy))
        result = image.copy(pixels)
        result.setDevicePixelRatio(1)
        return result

    def refresh_capture(self):
        if self.is_running or self._selecting or self.closing:
            return
        self._cancelled = False
        if self.region is None:
            if self.captured_image is not None:
                self.retry_translation()
            else:
                self.start_capture()
            return
        self._hide_capture_overlays()
        self.capture_started.emit()
        self._selecting = self._refreshing = True
        self._busy(True)
        self._status('Новый снимок выбранной области', 'busy')
        self._hide_window_for_capture()
        QTimer.singleShot(60, self._refresh_region)

    def _refresh_region(self):
        if self.closing or not self._refreshing:
            return
        try:
            screen = next((s for s in QApplication.screens() if s.geometry().contains(self.region)), None)
            if screen is None:
                raise RuntimeError('Область больше не помещается на экране. Выделите текст заново.')
            image = screen.grabWindow(0).toImage()
            if image.isNull():
                raise RuntimeError('Не удалось обновить снимок. Попробуйте выбрать область заново.')
            local = self.region.translated(-screen.geometry().x(), -screen.geometry().y())
            self.selected_screen = screen
            self.captured_image = self._crop_image(image, local, screen.geometry().size())
            self._clear_selectors()
            self._process_capture()
        except Exception as exc:
            self._clear_selectors()
            self._busy(False)
            self._failed(str(exc))

    def retry_translation(self):
        if self.is_running or self._selecting or self.closing:
            return
        if self.provider.currentData() != 'google':
            self.feedback.setText('Выберите Google для перевода. Отправляется только текст, не снимок.')
            return
        text = self.original.text.toPlainText().strip()
        if not text:
            if self.captured_image is not None:
                self._process_capture()
            return
        self.dismiss_overlay(restore=False)
        self._begin_processing()
        self._edited_text = text
        self.worker = TextTranslationWorker(text, self.source.currentData(), self.target.currentData(), self)
        self.worker.result.connect(self._text_result)
        self._connect_worker()

    def recognize_capture(self):
        if self.is_running or self._selecting or self.closing:
            return
        if self.captured_image is None:
            self.start_capture(local_only=True)
        else:
            self._ocr_only = True
            self._process_capture()

    def _begin_processing(self):
        self._busy(True)
        self._cancelled = False
        self.cancel_button.setEnabled(True)
        self.translated.text.clear()
        self._status('Переводим…', 'busy')
        self.feedback.setText('Дождитесь результата. Обработку можно отменить.')

    def _process_capture(self):
        self._begin_processing()
        self.last_lines = []
        self._set_source_text('')
        self.worker = TranslationWorker(self.captured_image, self.source.currentData(), self.target.currentData(), self)
        self.worker.provider = '' if self._ocr_only else self.provider.currentData()
        self._ocr_only = False
        self.worker.recognized.connect(self._recognized)
        self.worker.result.connect(self._result)
        self._connect_worker()

    def _recognized(self, text):
        if not self.closing and not self._cancelled:
            self._set_source_text(text)

    def _connect_worker(self):
        service = getattr(self.window(), 'agent_service', None)
        self.worker.secret_values = service.memory.secret_values if service else ()
        self.worker.failed.connect(self._failed)
        self.worker.progress.connect(self.feedback.setText)
        self.worker.progress.connect(lambda message: self._set_loading(True, message))
        self.worker.finished.connect(self._finished)
        self.worker.start(QThread.Priority.LowPriority)

    def _result(self, lines):
        if self.closing or self._cancelled:
            return
        self.last_lines = list(lines)
        self.translated.text.setPlainText('\n'.join(line.translation for line in lines))
        self._show_result(lines)
        confidence = [line.confidence for line in lines if getattr(line, 'confidence', None) is not None]
        if confidence and min(confidence) < 60:
            self.feedback.setText('Возможно, текст распознан неточно из-за шрифта или качества изображения')

    def _text_result(self, text):
        if self.closing or self._cancelled:
            return
        self.translated.text.setPlainText(text)
        source_lines, translated_lines = self._edited_text.splitlines(), text.splitlines()
        if self.last_lines and len(source_lines) == len(translated_lines) == len(self.last_lines):
            self.last_lines = [TextLine(source, original.rect, translated)
                for source, original, translated in zip(source_lines, self.last_lines, translated_lines)]
            self._show_result(self.last_lines)
        else:
            self._status('Перевод готов')
            self.feedback.setText('Готово. Скопируйте результат справа. Для показа на экране выделите соответствующий текст.')

    def _show_result(self, lines):
        self._capture_backup = None
        self.dismiss_overlay(restore=False)
        if not self.show_overlay.isChecked():
            self._status('Перевод готов')
            if self.region is not None:
                self._show_controls('\n'.join(line.translation or line.text for line in lines))
            return
        self.overlay = TranslationOverlay(self.region, self.captured_image, lines)
        self.overlay_controls = OverlayControls(self.selected_screen, self.region)
        self.overlay_controls.dismissed.connect(self.dismiss_overlay)
        self.overlay_controls.return_requested.connect(self._restore_window)
        self.overlay_controls.refresh_requested.connect(self.refresh_capture)
        self.overlay.show()
        self.overlay_controls.show()
        self._status('Перевод показан на экране')
        self.feedback.setText('«Обновить эту область» сделает свежий снимок. Перед перемещением окна уберите слой.')
        self._update_actions()

    def _failed(self, message):
        if self.closing or self._cancelled:
            return
        self._status('Не удалось перевести', 'error')
        self.feedback.setText(message)
        self.feedback.show()
        if self.region is None:
            self._restore_capture_overlays()
        if self.region is not None:
            self._show_controls(message)

    def _show_controls(self, text):
        if self.overlay_controls:
            self.overlay_controls.close()
            self.overlay_controls.deleteLater()
        screen = getattr(self, 'selected_screen', None) or QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.overlay_controls = OverlayControls(screen, self.region)
        self.overlay_controls.status_label.setText(text[:2000])
        self.overlay_controls.adjustSize()
        self.overlay_controls.reposition(screen, self.region)
        self.overlay_controls.dismissed.connect(self.dismiss_overlay)
        self.overlay_controls.refresh_requested.connect(self.refresh_capture)
        self.overlay_controls.show()

    def _finished(self):
        worker, self.worker = self.worker, None
        if worker:
            worker.deleteLater()
        self._busy(False)
        self.cancel_button.hide()
        if self._cancelled and not self.closing:
            self._restore_capture_overlays()
            self._status('Обработка отменена')
            self.feedback.setText('Можно выбрать другую область или перевести этот текст снова.')
        self.stopped.emit()

    def cancel_translation(self):
        self._cancelled = True
        if self.worker:
            self.worker.cancel.set()
        self.cancel_button.setEnabled(False)
        self._status('Отменяем…', 'busy')
        self.feedback.setText('Ожидаем завершения текущего запроса.')

    def dismiss_overlay(self, checked=False, restore=False):
        had_overlay = self.overlay is not None
        for widget in (self.overlay, self.overlay_controls):
            if widget:
                widget.close()
                widget.deleteLater()
        self.overlay = self.overlay_controls = None
        self._update_actions()
        if had_overlay:
            self._status('Перевод убран с экрана')
            if restore:
                self._restore_window()

    def shutdown(self):
        self.closing = True
        self._clear_selectors()
        self.dismiss_overlay(restore=False)
        if self.worker:
            self.worker.cancel.set()
