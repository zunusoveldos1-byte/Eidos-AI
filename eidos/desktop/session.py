import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4
from .applications import checked_executable


class SessionStore:
    def __init__(self, path, backend):
        self.path, self.backend = Path(path), backend
        self.lock = Lock()
        self._signature = None

    def snapshot(self):
        apps, seen = [], set()
        for row in self.backend.windows():
            try: path = checked_executable(row.get('launch_path', row['path']))
            except (ValueError, OSError): continue
            key = os.path.normcase(path)
            if key in seen: continue
            seen.add(key)
            apps.append({'name': Path(path).stem, 'path': path})
            if len(apps) >= 128: break
        return apps

    def save(self, *, changed_only=False):
        with self.lock:
            apps = self.snapshot()
            signature = tuple(sorted(os.path.normcase(a['path']) for a in apps))
            if changed_only and (not apps or signature == self._signature): return len(apps)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name('.session-' + uuid4().hex + '.json')
            try:
                temporary.write_text(json.dumps({'version': 1, 'updated': datetime.now(timezone.utc).isoformat(),
                    'applications': apps}, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(temporary, self.path)
                self._signature = signature
            finally: temporary.unlink(missing_ok=True)
            return len(apps)

    def restore(self, context):
        if not self.path.is_file(): return 'Сохранённой сессии пока нет.'
        if self.path.stat().st_size > 256000: raise ValueError('Файл сессии слишком велик')
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('applications'), list):
            raise ValueError('Неподдерживаемый формат сессии')
        running = {os.path.normcase(row.get('launch_path', row['path'])) for row in self.backend.windows()}
        seen, launched, missing, skipped = set(), 0, 0, 0
        for row in data['applications'][:128]:
            context.check()
            try:
                # Ignore arbitrary extra fields/arguments, never replay them.
                path = checked_executable(row['path'])
                key = os.path.normcase(path)
                if key in seen: continue
                seen.add(key)
                if key in running:
                    skipped += 1
                    continue
                self.backend.launch(path)
                launched += 1
                running.add(key)
                if context.cancel.wait(.15): context.check()
            except (InterruptedError, TimeoutError): raise
            except (OSError, ValueError, KeyError, TypeError): missing += 1
        ending = 'приложение' if launched % 10 == 1 and launched % 100 != 11 else 'приложения' if launched % 10 in (2, 3, 4) and launched % 100 not in (12, 13, 14) else 'приложений'
        return f'Запускаю {launched} {ending}. Не найдено: {missing}. Уже открыто: {skipped}.'
