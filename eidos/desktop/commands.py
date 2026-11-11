from threading import Lock
from time import monotonic
from pathlib import Path
from .intents import parse
from .browser import Browser
from .windows import WindowsBackend
from .applications import ApplicationCatalog
from .session import SessionStore
from .tasks import Tasks


class DesktopCommands:
    def __init__(self, settings, memory, root, backend=None, clock=monotonic):
        self.settings, self.backend, self.clock = settings, backend or WindowsBackend(), clock
        self.apps = ApplicationCatalog(settings, self.backend)
        self.browser = Browser(settings, self.backend)
        self.sessions = SessionStore(Path(root) / 'session.json', self.backend)
        self.tasks = Tasks(memory)
        self.ui = None
        self.pending = None
        self._lock = Lock()
        self._path_offered = set()

    def _ui(self, action, args, context):
        if self.ui is None: raise RuntimeError('Действие доступно в настольном интерфейсе Eidos')
        return self.ui(action, args, context.cancel)

    def cancel_pending(self):
        with self._lock: self.pending = None

    def handle(self, text, context):
        intent = parse(text)
        if intent is None: return None
        action, args = intent
        # Keep existing permission-checked Core Audio tools for sound.
        if action in ('volume', 'mute'): return None
        if context.origin != 'local':
            if action in ('browser', 'site', 'application', 'search_browser'):
                return None
            raise PermissionError('Эта команда доступна только локально в Eidos')
        context.check()
        self.apps.settings = self.settings
        if action == 'refuse': return args['text']
        if action == 'screenshot': return self._ui('screenshot', {**args, 'folder': self.settings.screenshot_folder}, context)
        if action == 'desktop':
            self.backend.desktop()
            return 'Показываю рабочий стол'
        if action == 'lock':
            self.backend.lock()
            return 'Экран заблокирован'
        if action == 'power':
            with self._lock: self.pending = (args['action'], self.clock() + 15)
            try:
                self._ui('power_prompt', args, context)
            except Exception:
                self.cancel_pending()
                raise
            return 'Подтвердите ' + ('выключение' if args['action'] == 'shutdown' else 'перезагрузку') + ' в течение 15 секунд.'
        if action == 'power_cancel':
            with self._lock: self.pending = None
            if self.ui: self._ui('power_hide', {}, context)
            return 'Действие отменено'
        if action == 'power_confirm':
            with self._lock:
                expected = self.pending
                if not expected or expected[0] != args['action'] or self.clock() >= expected[1]:
                    return 'Нет действующего подтверждения для этого действия.'
                self.pending = None
            self._ui('power_hide', {}, context)
            self.sessions.save()
            context.check()
            self.backend.power(args['action'])
            return 'Запрос питания передан Windows. Несохранённые данные могут остановить завершение.'
        if action == 'session_save': return f'Сессия сохранена: {self.sessions.save()} приложения.'
        if action == 'session_restore': return self.sessions.restore(context)
        if action == 'today': return self.tasks.today(self.settings.timezone)
        if action == 'task_add': return self.tasks.add(args['title'], self.settings.timezone)
        if action == 'schedule':
            from eidos.agent.tools import LocalCalendar
            from datetime import datetime
            from zoneinfo import ZoneInfo
            zone = ZoneInfo(self.settings.timezone)
            today = datetime.now(zone).date()
            rows = [row for row in LocalCalendar(self.tasks.memory).list()
                    if datetime.fromisoformat(row['start']).astimezone(zone).date() == today]
            return ('Локальный календарь, без внешней синхронизации:\n' + '\n'.join(row['title'] for row in rows)) if rows else 'В локальном календаре на сегодня встреч нет. Внешний календарь не подключён.'
        if action in ('browser', 'site', 'search_browser'):
            self.browser.settings = self.settings
            return self.browser.open(action, args)
        if action == 'application':
            result = self.apps.open(args['name'])
            if result: return result
            key = args['name'].casefold()
            if key not in self._path_offered:
                self._path_offered.add(key)
                if self.ui:
                    path = self._ui('application_path', args, context)
                    if path:
                        from .applications import checked_executable
                        self.settings.approved_apps[args['name']] = checked_executable(path)
                        if hasattr(self, 'save_settings'): self.save_settings(self.settings)
                        return self.apps.open(args['name'])
            return 'Приложение не найдено. Укажите EXE в списке приложений Eidos; для сайта уточните адрес.'
        if action == 'volume_status':
            from eidos.agent.tools import audio
            return audio({}, context, status=True).text
        return None
