"""Real local tasks, with a small replaceable external-provider boundary."""
from datetime import datetime, date
from zoneinfo import ZoneInfo


class Tasks:
    def __init__(self, memory):
        self.memory = memory
        self.provider = None  # No pretend Google Tasks connection.
        with memory.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS desktop_tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL, due TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS desktop_task_cache(source TEXT PRIMARY KEY, content TEXT NOT NULL)')

    def connect_provider(self, provider):
        """Provider.fetch() returns actual rows: title, due ISO date, completed."""
        self.provider = provider

    def add(self, title, zone):
        if not title.strip() or len(title) > 1000: raise ValueError('Некорректное название задачи')
        today = datetime.now(ZoneInfo(zone)).date().isoformat()
        with self.memory.connect() as db:
            db.execute('INSERT INTO desktop_tasks(title,due) VALUES(?,?)', (title.strip(), today))
        return 'Задача на сегодня сохранена: ' + title.strip()

    def today(self, zone):
        current = datetime.now(ZoneInfo(zone)).date()
        cached = False
        if self.provider is not None:
            if not getattr(self.provider, 'connected', True): return 'Источник задач не подключён.'
            source = getattr(self.provider, 'name', type(self.provider).__name__)
            import json
            try:
                rows = list(self.provider.fetch())
                with self.memory.connect() as db:
                    db.execute('INSERT OR REPLACE INTO desktop_task_cache(source,content) VALUES(?,?)',
                               (source, json.dumps(rows, ensure_ascii=False)))
            except (OSError, ConnectionError, TimeoutError):
                with self.memory.connect() as db:
                    result = db.execute('SELECT content FROM desktop_task_cache WHERE source=?', (source,)).fetchone()
                if not result: return 'Источник задач временно недоступен. Сохранённых данных нет.'
                rows, cached = json.loads(result['content']), True
        else:
            with self.memory.connect() as db:
                rows = [dict(row) for row in db.execute('SELECT * FROM desktop_tasks WHERE completed=0 ORDER BY due,id LIMIT 200')]
        today, overdue = [], []
        for row in rows:
            if row.get('completed'): continue
            due = date.fromisoformat(row['due'][:10])
            if due == current: today.append(row['title'])
            elif due < current: overdue.append(row['title'])
        if not today and not overdue: return ('Сохранённые данные. ' if cached else '') + 'На сегодня задач нет.'
        # First sentences are the short speech summary; full list remains in UI.
        brief = f'На сегодня задач: {len(today)}. Просроченных: {len(overdue)}. '
        brief += 'Первые задачи: ' + '; '.join((today + overdue)[:3]) + '.\n'
        return ('Сохранённые данные. ' if cached else '') + brief + '\n'.join(
            ['Сегодня:'] + ['• ' + title for title in today] + ['Просроченные:'] + ['• ' + title for title in overdue])
