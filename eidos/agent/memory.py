"""SQLite data, FTS5 retrieval and durable delivery reservations; no training."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
import sqlite3

KINDS = ('dialogue', 'profile', 'preference', 'project', 'summary')
SECRET = re.compile(r'(?:sk-[\w-]{12,}|\d{7,}:[\w-]{20,}|[\w-]{20,}\.[\w-]{6,}\.[\w-]{20,}|(?:password|пароль|token|токен|api[_ -]?key|ключ api)\s*[:=]\s*\S+|(?:мой пароль|мой токен|my password|my token)\s+(?:это\s+)?\S+)', re.I)


def has_secret(text: str, values: tuple[str, ...] = ()) -> bool:
    return bool(SECRET.search(text)) or any(value in text for value in values if value)


def require_public_text(text: str, values: tuple[str, ...] = ()) -> None:
    """Fail closed before external text transport; never include input in errors."""
    if has_secret(text, values):
        raise ValueError('Обнаружен возможный секрет. Внешняя отправка отменена.')


def require_public_payload(payload, values: tuple[str, ...] = ()) -> None:
    """Check raw strings before JSON escaping changes exact credential matches."""
    if isinstance(payload, str):
        require_public_text(payload, values)
    elif isinstance(payload, dict):
        for key, value in payload.items():
            require_public_text(str(key), values)
            require_public_payload(value, values)
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            require_public_payload(value, values)


def redact_secrets(text: str, values: tuple[str, ...] = ()) -> str:
    for value in sorted(values, key=len, reverse=True):
        if value:
            text = text.replace(value, '[секрет скрыт]')
    return SECRET.sub('[секрет скрыт]', text)


class Memory:
    def __init__(self, path: Path, *, max_rows=10000, retention_days=365):
        self.path = path
        self.max_rows = max(1, int(max_rows))
        self.retention_days = max(1, int(retention_days))
        self.secret_values: tuple[str, ...] = ()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            # Never overwrite or recreate a corrupt database silently.
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise sqlite3.DatabaseError('Локальная база повреждена. Сохраните копию перед восстановлением.')
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, content TEXT NOT NULL,
                    source TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(content,
                    content=memories, content_rowid=id, tokenize='unicode61');
                CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memories BEGIN
                    INSERT INTO memory_fts(rowid,content) VALUES (new.id,new.content); END;
                CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memories BEGIN
                    INSERT INTO memory_fts(memory_fts,rowid,content) VALUES ('delete',old.id,old.content); END;
                CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memories BEGIN
                    INSERT INTO memory_fts(memory_fts,rowid,content) VALUES ('delete',old.id,old.content);
                    INSERT INTO memory_fts(rowid,content) VALUES(new.id,new.content); END;
                CREATE TABLE IF NOT EXISTS deliveries (id TEXT PRIMARY KEY, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, start TEXT NOT NULL,
                    timezone TEXT NOT NULL, reminder_minutes INTEGER NOT NULL DEFAULT 10,
                    notified INTEGER NOT NULL DEFAULT 0);
            ''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(memories)')}
            if 'evidence' not in columns:
                db.execute("ALTER TABLE memories ADD COLUMN evidence TEXT NOT NULL DEFAULT 'unconfirmed'")
                # Existing rows must be indexed before UPDATE triggers issue
                # FTS delete records (also supports pre-FTS legacy databases).
                db.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
                db.execute("UPDATE memories SET evidence=CASE WHEN kind='summary' THEN 'inference' "
                           "WHEN kind='dialogue' THEN 'transcript' WHEN kind='preference' THEN 'preference' "
                           "ELSE 'unconfirmed' END")
            db.execute('PRAGMA user_version=1')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA secure_delete=ON')
        return db

    def add(self, kind: str, content: str, source: str, *, evidence=None) -> int | None:
        if kind not in KINDS or not content.strip() or len(content) > 16000:
            raise ValueError('Некорректная запись памяти')
        if has_secret(content, self.secret_values) or has_secret(source, self.secret_values):
            return None
        if len(source) > 1000:
            raise ValueError('Слишком длинный источник записи памяти')
        evidence = evidence or {'summary': 'inference', 'dialogue': 'transcript',
                               'preference': 'preference'}.get(kind, 'unconfirmed')
        if evidence not in ('confirmed', 'preference', 'inference', 'transcript', 'unconfirmed'):
            raise ValueError('Некорректный тип подтверждения памяти')
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            ident = db.execute('INSERT INTO memories(kind,content,source,created,updated,evidence) VALUES(?,?,?,?,?,?)',
                              (kind, content, source, now, now, evidence)).lastrowid
            self._prune(db)
            return ident

    def _prune(self, db):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        db.execute('DELETE FROM memories WHERE updated < ?', (cutoff,))
        db.execute('DELETE FROM memories WHERE id NOT IN (SELECT id FROM memories ORDER BY id DESC LIMIT ?)',
                   (self.max_rows,))

    def prune(self):
        with self.connect() as db:
            self._prune(db)

    def items(self, kind: str | None = None, limit: int = 200):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM memories WHERE (? IS NULL OR kind=?) ORDER BY id DESC LIMIT ?', (kind, kind, min(limit, 200)))
            return [self._safe_row(row) for row in rows]

    def _safe_row(self, row):
        result = dict(row)
        for key in ('content', 'source'):
            result[key] = redact_secrets(result[key], self.secret_values)
        return result

    def search(self, query: str, limit: int = 5):
        terms = re.findall(r'\w+', query, flags=re.UNICODE)[:16]
        if not terms or has_secret(query, self.secret_values):
            return []
        match = ' OR '.join('"' + term.replace('"', '') + '"' for term in terms)
        with self.connect() as db:
            rows = db.execute('SELECT m.* FROM memory_fts f JOIN memories m ON m.id=f.rowid '
                              'WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?', (match, min(limit, 10)))
            return [self._safe_row(row) for row in rows]

    def edit(self, ident: int, content: str, source: str):
        if not content.strip() or len(content) > 16000 or has_secret(content, self.secret_values) or has_secret(source, self.secret_values):
            raise ValueError('Пустая запись, превышение размера или секрет')
        with self.connect() as db:
            db.execute('UPDATE memories SET content=?,source=?,updated=? WHERE id=?',
                       (content, source, datetime.now(timezone.utc).isoformat(), ident))

    def delete(self, ident: int):
        with self.connect() as db:
            db.execute('DELETE FROM memories WHERE id=?', (ident,))

    def clear(self, history_only: bool = False):
        with self.connect() as db:
            if history_only:
                db.execute("DELETE FROM memories WHERE kind IN ('dialogue','summary')")
            else:
                db.execute('DELETE FROM memories')
            db.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        with self.connect() as db:
            db.execute('VACUUM')

    def reserve_delivery(self, ident: str) -> bool:
        with self.connect() as db:
            return db.execute("INSERT OR IGNORE INTO deliveries VALUES(?, 'pending')", (ident,)).rowcount == 1

    def delivery_status(self, ident: str, status: str):
        with self.connect() as db:
            db.execute('UPDATE deliveries SET status=? WHERE id=?', (status, ident))
