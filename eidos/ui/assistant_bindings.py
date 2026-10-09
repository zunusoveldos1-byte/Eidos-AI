"""UI wiring for the assistant; all network/model/tool operations are queued."""
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from PyQt6.QtCore import QDateTime, QTimer, Qt, QSignalBlocker
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QListWidgetItem, QMessageBox

from eidos.agent.controller import AgentController
from eidos.agent.harness import TaskContext
from eidos.agent.memory import has_secret
from eidos.agent.skills import catalog
from .pages.assistant import Onboarding


class VoiceAgentProvider:
    def __init__(self, service, voice_worker, agent_worker):
        self.service, self.voice_worker, self.agent_worker = service, voice_worker, agent_worker

    def respond(self, text):
        context = self.service.context(cancel=self.voice_worker.cancel_event, incognito=self.service.incognito)
        context.confirm = lambda action: self.agent_worker.confirm(action, context)
        context.progress = self.voice_worker.agent_progress.emit
        return self.service.respond(text, context)

    def handle(self, text):
        return self.respond(text)


class AssistantBindings:
    def _init_agent(self, show_onboarding=False):
        self.agent_controller = AgentController(self.agent_service, self)
        controller, ui = self.agent_controller, self.assistant
        self._approval_boxes = []
        self._pending_incoming = []
        self._last_agent_error = ''
        self._agent_had_error = False
        controller.progress.connect(self._agent_progress)
        controller.answer.connect(self._agent_answer)
        controller.data.connect(self._agent_data)
        controller.error.connect(self._agent_error)
        controller.finished.connect(self._agent_finished)
        controller.confirmation.connect(self._agent_confirm)
        controller.closed.connect(self._closed)
        self.controller.worker.commands = VoiceAgentProvider(self.agent_service, self.controller.worker, controller.worker)
        ui.incognito.toggled.connect(lambda enabled:setattr(self.agent_service,'incognito',enabled))
        self.controller.agent_progress.connect(self._voice_agent_progress)
        ui.send.clicked.connect(self._send_chat)
        ui.stop.clicked.connect(self._stop_agent)
        ui.select_files.clicked.connect(self._select_agent_files)
        ui.select_folder.clicked.connect(self._select_agent_folder)
        ui.forget_files.clicked.connect(self._forget_agent_files)
        ui.document_read_button.clicked.connect(self._read_selected_document)
        ui.document_write_button.clicked.connect(self._create_document)
        ui.memory_refresh.clicked.connect(self._refresh_memory)
        ui.memory_kind.currentIndexChanged.connect(self._refresh_memory)
        ui.memory_list.currentItemChanged.connect(self._memory_selected)
        ui.memory_save.clicked.connect(self._save_memory)
        ui.memory_new.clicked.connect(lambda: (ui.memory_list.setCurrentRow(-1), ui.memory_edit.clear()))
        ui.memory_delete.clicked.connect(self._delete_memory)
        ui.history_clear.clicked.connect(lambda: self._clear_memory(True))
        ui.memory_clear.clicked.connect(lambda: self._clear_memory(False))
        ui.memory_enabled.toggled.connect(self._set_memory_enabled)
        ui.event_refresh.clicked.connect(self._refresh_calendar)
        ui.calendar_list.currentItemChanged.connect(self._calendar_selected)
        for mode, control in [('create',ui.event_create), ('update',ui.event_update), ('delete',ui.event_delete)]:
            control.clicked.connect(lambda checked=False, m=mode: self._calendar_change(m))
        ui.skills_list.currentItemChanged.connect(self._skill_selected)
        ui.connections_save.clicked.connect(self._save_connections)
        ui.search_test.clicked.connect(lambda:self._start_agent_task('search_test'))
        ui.secret_delete_button.clicked.connect(self._delete_secret)
        for kind, control in ui.bot_tests.items():
            control.clicked.connect(lambda checked=False, k=kind: self._start_agent_task('test_'+k))
        ui.model_save.clicked.connect(self._save_model)
        ui.server_start.clicked.connect(lambda: self._start_agent_task('start'))
        ui.model_pull.clicked.connect(self._pull_model)
        ui.model_test.clicked.connect(lambda: self._start_agent_task('model_test'))
        ui.hardware_test.clicked.connect(lambda: self._start_agent_task('hardware'))
        ui.profile_save.clicked.connect(self._save_profile)
        ui.app_add.clicked.connect(self._add_app)
        ui.app_remove.clicked.connect(self._remove_app)
        self._refresh_apps()
        self._refresh_memory()
        self._refresh_calendar()
        self._refresh_skills()
        self._restore_history()
        self._profile_hints()
        if self.agent_service.store.warning:
            ui.feedback.setText(self.agent_service.store.warning)
        self._agent_poll = QTimer(self)
        self._agent_poll.setInterval(5000)
        self._agent_poll.timeout.connect(self._poll_channels)
        self._agent_poll.start()
        self._reminders = QTimer(self)
        self._reminders.setInterval(30000)
        self._reminders.timeout.connect(self._show_reminders)
        self._reminders.start()
        if show_onboarding and not self.agent_service.settings.onboarding_done and not os.environ.get('EIDOS_SKIP_ONBOARDING'):
            QTimer.singleShot(600, self._show_onboarding)

    def _start_agent_task(self, kind, payload=None):
        if hasattr(self, 'background') and self.background.speech.active:
            self.background.stop_speech()
        if self.controller.active or self.controller.playback.active or self.controller.closing:
            self.assistant.feedback.setText('Дождитесь завершения голосовой операции.')
            return False
        if hasattr(self, 'background'):
            self.background.stop_speech()
            self.background.wake.set_busy(True)
        self._agent_had_error = False
        started = self.agent_controller.start(kind, payload, incognito=self.assistant.incognito.isChecked())
        if started:
            self._agent_controls()
            self._update_controls()
        return started

    def _agent_controls(self):
        ui = self.assistant
        busy = self.agent_controller.active or self.controller.active
        speaking = hasattr(self, 'background') and self.background.speech.active
        ui.stop.setEnabled(busy or speaking)
        for control in (ui.send, ui.incognito, ui.select_files, ui.select_folder, ui.forget_files, ui.document_read_button,
                        ui.document_write_button, ui.model_save, ui.server_start, ui.model_pull, ui.model_test,
                        ui.hardware_test, ui.connections_save, ui.search_test, ui.secret_delete_button, ui.profile_save,
                        ui.memory_save, ui.memory_delete, ui.memory_clear, ui.history_clear, ui.memory_enabled,
                        ui.event_create, ui.event_update, ui.event_delete, ui.app_add, ui.app_remove, *ui.bot_tests.values()):
            control.setEnabled(not busy and not self.agent_controller.closing)

    def _send_chat(self):
        text = self.assistant.input.toPlainText().strip()
        if not text:
            return
        if has_secret(text, self.agent_service.memory.secret_values):
            self.assistant.feedback.setText('Введите секрет во вкладке «Подключения». Запрос не отправлен.')
            return
        if self._start_agent_task('chat', text):
            self.assistant.history.appendPlainText('Вы\n' + text + '\n')
            self.assistant.input.clear()

    def _stop_agent(self):
        if hasattr(self, 'background'):
            self.background.stop_speech()
        self.agent_controller.cancel()
        if self.controller.active:
            self.controller.stop()
        self.assistant.task_status.setText('Запрошена отмена…')
        self.assistant.stop.setEnabled(False)

    def _agent_progress(self, state, text):
        self.assistant.task_status.setText(text)
        self.assistant.mascot.set_state('acting' if state in ('acting','checking') else 'thinking')
        self.sidebar.logo.set_state(self.assistant.mascot.state)
        if hasattr(self, 'background'):
            self.background.status('acting' if state in ('acting', 'checking') else 'thinking', text)
        self.assistant.journal.appendPlainText(f'{datetime.now():%H:%M:%S}  {text}')

    def _voice_agent_progress(self, state, text):
        if self.controller.closing or self.controller.cancelling:
            return
        self.voice.title.setText('Выполняю действие' if state in ('acting','checking') else 'Обрабатываю запрос')
        self.voice.operation.setText(text)
        self.voice.mascot.set_state('acting' if state in ('acting','checking') else 'thinking')
        self.sidebar.logo.set_state(self.voice.mascot.state)
        if hasattr(self, 'background'):
            self.background.status('acting' if state in ('acting', 'checking') else 'thinking', text)
        self._log(text)

    def _agent_answer(self, text):
        self.assistant.history.appendPlainText('Eidos\n' + text + '\n')
        if self.config.speak and hasattr(self, 'background'):
            self.background.speak(text)

    def _agent_error(self, message):
        self._agent_had_error = True
        self.assistant.task_status.setText(message)
        self.assistant.mascot.set_state('error')
        self.assistant.feedback.setText(message)
        if hasattr(self, 'background'):
            self.background.status('error', message)
        if message != self._last_agent_error:
            self.assistant.journal.appendPlainText(message)
            self._last_agent_error = message

    def _agent_data(self, kind, data):
        if kind == 'receive':
            self._pending_incoming.extend(data[:max(0, 20-len(self._pending_incoming))])
        elif kind in ('hardware','model_test'):
            self.assistant.hardware_display.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            self.assistant.feedback.setText(str(data))
            if kind == 'tool':
                self.assistant.history.appendPlainText('Инструмент\n' + str(data) + '\n')
            elif kind.startswith('memory_'):
                self.assistant.memory_edit.clear()
                if kind == 'memory_clear':
                    self.assistant.history.clear()
        self._refresh_calendar()

    def _agent_finished(self):
        if not self._agent_had_error:
            self.assistant.task_status.setText('Готов к запросу')
            self.assistant.mascot.set_state('ready')
            self.sidebar.logo.set_state('ready')
            if hasattr(self, 'background') and not self.background.speech.active:
                self.background.status('ready', 'Готов к запросу')
        self._agent_controls()
        self._update_controls()
        self._refresh_memory()
        self._refresh_skills()
        self._profile_hints()
        if self._pending_incoming and not self.agent_controller.closing:
            incoming = self._pending_incoming.pop(0)
            QTimer.singleShot(0, lambda: self._start_agent_task('remote', incoming))

    def _agent_confirm(self, approval):
        if self.controller.closing or self.agent_controller.closing:
            approval.event.set()
            return
        box = QMessageBox(self)
        box.setWindowTitle('Подтвердить действие Eidos')
        box.setIcon(QMessageBox.Icon.Question)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(approval.action)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        self._approval_boxes.append(box)
        def finish(result):
            approval.accepted = result == int(QMessageBox.StandardButton.Yes)
            approval.event.set()
            if box in self._approval_boxes:
                self._approval_boxes.remove(box)
            box.deleteLater()
        box.finished.connect(finish)
        box.open()

    def _select_agent_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Выберите документы', '', 'Документы (*.txt *.md *.docx *.xlsx *.pdf)')
        self.agent_service.files.update(str(Path(p).resolve()) for p in files)
        self._update_grants()

    def _select_agent_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Рабочая папка для поиска и новых документов')
        if folder:
            path = Path(folder).resolve()
            if path == Path(path.anchor):
                self.assistant.feedback.setText('Выберите конкретную папку, а не весь диск.')
                return
            self.agent_service.folders.add(str(path))
        self._update_grants()

    def _forget_agent_files(self):
        self.agent_service.files.clear()
        self.agent_service.folders.clear()
        self._update_grants()

    def _update_grants(self):
        self.assistant.grants.setText('Файлы: ' + '\n'.join(sorted(self.agent_service.files)) + '\nПапки: ' + '\n'.join(sorted(self.agent_service.folders)))

    def _read_selected_document(self):
        files = sorted(self.agent_service.files)
        if not files:
            self._select_agent_files()
            files = sorted(self.agent_service.files)
        if not files:
            return
        selected, accepted = QInputDialog.getItem(self, 'Прочитать документ', 'Выбранные файлы', files, 0, False)
        if accepted:
            self._start_agent_task('tool', ('document_read', {'path': selected}))

    def _create_document(self):
        content, accepted = QInputDialog.getMultiLineText(self, 'Создать документ', 'Текст нового документа (для XLSX — TSV)', self.assistant.input.toPlainText())
        if not accepted or not content.strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Сохранить новую версию', '', 'Markdown (*.md);;Текст (*.txt);;Word (*.docx);;Excel (*.xlsx);;PDF (*.pdf)')
        if path:
            parent = Path(path).resolve().parent
            if parent == Path(parent.anchor):
                self.assistant.feedback.setText('Выберите папку, а не корень диска.')
                return
            self.agent_service.folders.add(str(parent))
            self._update_grants()
            self._start_agent_task('tool', ('document_write', {'path': path, 'content': content}))

    def _restore_history(self):
        if self.agent_service.settings.memory_enabled:
            for item in reversed(self.agent_service.memory.items('dialogue', 6)):
                self.assistant.history.appendPlainText(item['content'] + '\n')

    def _refresh_memory(self, *args):
        ui = self.assistant
        search = ui.memory_search.text().strip()
        items = self.agent_service.memory.search(search, 10) if search else self.agent_service.memory.items(ui.memory_kind.currentData())
        ui.memory_list.clear()
        for data in items:
            item = QListWidgetItem(f"{data['kind']} · {data['updated'][:10]} · {data['content'][:80].replace(chr(10),' ')}")
            item.setData(Qt.ItemDataRole.UserRole, data)
            item.setToolTip('Источник: ' + data['source'])
            ui.memory_list.addItem(item)

    def _memory_selected(self, current, previous=None):
        if current:
            data = current.data(Qt.ItemDataRole.UserRole)
            self.assistant.memory_edit.setPlainText(data['content'])
            self.assistant.memory_source.setText(data['source'])

    def _save_memory(self):
        ui = self.assistant
        if not self.agent_service.settings.memory_enabled:
            ui.feedback.setText('Сначала включите постоянную память.')
            return
        current = ui.memory_list.currentItem()
        self._start_agent_task('memory_save', {'id': current.data(Qt.ItemDataRole.UserRole)['id'] if current else None,
            'content':ui.memory_edit.toPlainText(), 'source':ui.memory_source.text(), 'kind':ui.fact_kind.currentData()})

    def _ask(self, title, text):
        return QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _delete_memory(self):
        current = self.assistant.memory_list.currentItem()
        if current and self._ask('Удалить запись?', current.data(Qt.ItemDataRole.UserRole)['content'][:500]):
            self._start_agent_task('memory_delete', current.data(Qt.ItemDataRole.UserRole)['id'])

    def _clear_memory(self, history_only):
        title = 'Очистить историю диалогов и итоги?' if history_only else 'Удалить все записи памяти?'
        if self._ask(title, 'Данные будут удалены из локальной SQLite-памяти. Календарь и профиль в настройках сохранятся.'):
            self._start_agent_task('memory_clear', history_only)

    def _set_memory_enabled(self, enabled):
        target = replace(self.agent_service.settings, memory_enabled=enabled)
        if not enabled:
            # Turning memory off takes effect even if the settings disk becomes unwritable.
            self.agent_service.settings.memory_enabled = False
            self.agent_service.history.clear()
        saved = self._save_agent_settings(target)
        actual = self.agent_service.settings.memory_enabled
        blocker = QSignalBlocker(self.assistant.memory_enabled)
        self.assistant.memory_enabled.setChecked(actual)
        del blocker
        self.assistant.profile.memory.setChecked(actual)
        if not saved and not enabled:
            self.assistant.feedback.setText('Память выключена в текущем запуске. Настройки не записались; после перезапуска проверьте переключатель.')

    def _save_agent_settings(self, settings):
        if self.agent_controller.active or self.controller.active:
            self.assistant.feedback.setText('Дождитесь текущей операции.')
            return False
        try:
            self.agent_service.save_settings(settings)
            self.assistant.feedback.setText('Настройки ассистента сохранены.')
            self._refresh_skills()
            return True
        except Exception as exc:
            self.assistant.feedback.setText(str(exc) if isinstance(exc, ValueError) else 'Настройки не сохранены; проверьте доступ к профилю.')
            return False

    def _refresh_calendar(self):
        self.assistant.calendar_list.clear()
        for event in self.agent_service.calendar.list():
            start = datetime.fromisoformat(event['start']).astimezone(ZoneInfo(event['timezone']))
            item = QListWidgetItem(f"#{event['id']} · {start:%d.%m.%Y %H:%M} ({event['timezone']}) · {event['title']}")
            item.setData(Qt.ItemDataRole.UserRole, event)
            self.assistant.calendar_list.addItem(item)

    def _calendar_selected(self, current, previous=None):
        if current:
            event = current.data(Qt.ItemDataRole.UserRole)
            ui = self.assistant
            ui.event_title.setText(event['title'])
            start = datetime.fromisoformat(event['start']).astimezone(ZoneInfo(event['timezone']))
            ui.event_start.setDateTime(QDateTime(start.replace(tzinfo=None)))
            ui.event_zone.setText(event['timezone'])
            ui.event_reminder.setValue(event['reminder_minutes'])

    def _calendar_change(self, mode):
        ui = self.assistant
        item = ui.calendar_list.currentItem()
        if mode != 'create' and not item:
            ui.feedback.setText('Выберите событие.')
            return
        args = {'mode': mode, 'id': item.data(Qt.ItemDataRole.UserRole)['id'] if item else 0,
                'title': ui.event_title.text(), 'start': ui.event_start.dateTime().toString('yyyy-MM-ddTHH:mm:ss'),
                'timezone': ui.event_zone.text(), 'reminder_minutes': ui.event_reminder.value()}
        self._start_agent_task('tool', ('calendar_change', args))

    def _show_reminders(self):
        if self.agent_controller.closing:
            return
        for event in self.agent_service.calendar.due():
            box = QMessageBox(QMessageBox.Icon.Information, 'Напоминание Eidos', event['title'], parent=self)
            box.setTextFormat(Qt.TextFormat.PlainText)
            box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            box.open()

    def _refresh_skills(self):
        self.assistant.skills_list.clear()
        search_ready = True
        if self.agent_service.settings.search_provider == 'brave':
            try:
                search_ready = bool(self.agent_service.secrets.get('brave'))
            except Exception:
                search_ready = False
        for skill in catalog(self.agent_service.model_connected, search_ready):
            item = QListWidgetItem(skill.name + '  ·  ' + skill.status)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self.assistant.skills_list.addItem(item)
        self.assistant.skills_list.setCurrentRow(0)

    def _skill_selected(self, current, previous=None):
        if current:
            skill = current.data(Qt.ItemDataRole.UserRole)
            self.assistant.skill_detail.setText(skill.purpose + '\nТребования: ' + skill.requirements + '\nИнструменты: ' + ', '.join(skill.tools) + '\nРазрешения: ' + ', '.join(skill.permissions))

    def _save_connections(self):
        ui = self.assistant
        settings = replace(self.agent_service.settings, remote_permissions=[p for p, c in ui.remote_checks.items() if c.isChecked()])
        for kind in ('telegram','discord'):
            setattr(settings, kind+'_enabled', ui.bot_enabled[kind].isChecked())
            for suffix, control in [('users',ui.bot_users[kind]), ('channels',ui.bot_channels[kind])]:
                setattr(settings, kind+'_'+suffix, [s.strip() for s in control.text().split(',') if s.strip()])
        try:
            settings.validate()
            for kind, control in ui.secrets_edits.items():
                if control.text().strip():
                    self.agent_service.secrets.set(kind, control.text())
                    control.clear()
            self.agent_service.memory.secret_values = self.agent_service.secrets.values()
            self._save_agent_settings(settings)
        except Exception:
            ui.feedback.setText('Подключения не сохранены: проверьте числовые ID и доступ к Credential Manager.')

    def _delete_secret(self):
        kind = self.assistant.secret_delete.currentText()
        if self._ask('Удалить секрет?', 'Удалить ' + kind + ' из Windows Credential Manager?'):
            try:
                self.agent_service.secrets.delete(kind)
                self.agent_service.memory.secret_values = self.agent_service.secrets.values()
                self.assistant.feedback.setText('Секрет удалён.')
            except Exception:
                self.assistant.feedback.setText('Не удалось удалить секрет.')

    def _save_model(self):
        ui = self.assistant
        self._save_agent_settings(replace(self.agent_service.settings, provider=ui.provider.currentData(), model=ui.model_name.text().strip(),
            cloud_model=ui.cloud_model.text().strip(), ollama_url=ui.ollama_url.text().strip(), context_size=ui.context_size.value(), search_provider=ui.search_provider.currentData()))

    def _pull_model(self):
        model = self.agent_service.settings.model
        size = {'qwen3:4b':'2,5 ГБ', 'qwen3:4b-instruct-2507-q4_K_M':'2,5 ГБ', 'qwen3:1.7b':'1,4 ГБ'}.get(model, 'размер зависит от модели; проверьте каталог ollama.com')
        if self._ask('Загрузить локальную модель?', f'{model}\nРазмер: {size}\nКонтекст: {self.agent_service.settings.context_size}\nНужен интернет и место на диске.'):
            self._start_agent_task('pull')

    def _save_profile(self):
        values = self.assistant.profile.values()
        if self._save_agent_settings(replace(self.agent_service.settings, **values)):
            self.assistant.memory_enabled.setChecked(values['memory_enabled'])
            self._profile_hints()
            if values['memory_enabled']:
                self.agent_service.memory.add('profile', json.dumps(values, ensure_ascii=False), 'Ответы пользователя в профиле')

    def _show_onboarding(self):
        if self.controller.closing or self.agent_controller.closing:
            return
        dialog = Onboarding(self.agent_service.settings, self)
        self._onboarding = dialog
        def done(result):
            if not self.agent_controller.closing:
                values = dialog.form.values() if result else {'onboarding_done': True}
                if self._save_agent_settings(replace(self.agent_service.settings, **values)):
                    self.assistant.profile.name.setText(self.agent_service.settings.name)
                    self.assistant.profile.tasks.setPlainText(self.agent_service.settings.tasks)
                    self.assistant.profile.language.setCurrentText(self.agent_service.settings.language)
                    self.assistant.memory_enabled.setChecked(self.agent_service.settings.memory_enabled)
                    self._profile_hints()
                    from eidos.agent.settings import PROFESSIONS
                    for index, name in enumerate(PROFESSIONS):
                        self.assistant.profile.professions.item(index).setCheckState(Qt.CheckState.Checked if name in self.agent_service.settings.professions else Qt.CheckState.Unchecked)
            dialog.deleteLater()
        dialog.finished.connect(done)
        dialog.open()

    def _profile_hints(self):
        suggestions = {
            'Программист': 'Объясни ошибку в Python', 'Дизайнер': 'Помоги составить дизайн-бриф',
            'Photoshop / обработка фото': 'Предложи план обработки фото',
            '3D-художник / аниматор': 'Помоги спланировать 3D-сцену',
            'Видеомонтажёр': 'Помоги составить монтажный план', 'Студент': 'Объясни учебную тему',
            'Преподаватель': 'Помоги подготовить занятие', 'Работа с документами': 'Составь черновик документа',
            'Предприниматель': 'Помоги спланировать проект'}
        hints = [suggestions[p] for p in self.agent_service.settings.professions if p in suggestions][:3]
        default_hint = ('Модель ответила успешно. Можно задать следующий вопрос; команды Windows работают без LLM.'
                        if self.agent_service.model_connected else
                        'Команды Windows работают без модели. Для свободного диалога подключите модель во вкладке «Модель».')
        self.assistant.profile_hint.setText('Попробуйте: ' + ' · '.join(hints) if hints else default_hint)
        self.assistant.input.setPlaceholderText((hints[0] if hints else 'Сделай громкость 30 процентов') + ' — или введите свой запрос')

    def _refresh_apps(self):
        self.assistant.apps_list.clear()
        self.assistant.apps_list.addItems(sorted(self.agent_service.settings.approved_apps))

    def _add_app(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Разрешить запуск приложения', '', 'Приложение (*.exe)')
        if path:
            apps = dict(self.agent_service.settings.approved_apps)
            apps[Path(path).stem] = str(Path(path).resolve())
            if self._save_agent_settings(replace(self.agent_service.settings, approved_apps=apps)):
                self._refresh_apps()

    def _remove_app(self):
        name = self.assistant.apps_list.currentText()
        apps = dict(self.agent_service.settings.approved_apps)
        apps.pop(name, None)
        if self._save_agent_settings(replace(self.agent_service.settings, approved_apps=apps)):
            self._refresh_apps()

    def _poll_channels(self):
        if self.agent_controller.active or self.agent_controller.closing or self.controller.active or self.controller.playback.active:
            return
        if self.agent_service.settings.telegram_enabled or self.agent_service.settings.discord_enabled:
            self._start_agent_task('receive')

    def _shutdown_agent(self):
        self._agent_poll.stop()
        self._reminders.stop()
        self.agent_controller.shutdown()
        for box in list(self._approval_boxes):
            box.reject()
        if hasattr(self, '_onboarding'):
            try:
                self._onboarding.reject()
            except RuntimeError:
                pass
