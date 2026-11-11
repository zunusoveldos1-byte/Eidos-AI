import sqlite3
from eidos.agent.memory import Memory


def test_migration_preserves_old_rows_and_marks_model_summaries(tmp_path):
    path = tmp_path / 'memory.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE memories(id INTEGER PRIMARY KEY,kind TEXT,content TEXT,source TEXT,created TEXT,updated TEXT)')
        db.execute("INSERT INTO memories VALUES(1,'summary','unconfirmed inference','model','2026-10-13','2026-10-13')")
    memory = Memory(path)
    assert memory.items()[0]['evidence'] == 'inference'
    assert memory.items()[0]['content'] == 'unconfirmed inference'
    assert memory.search('unconfirmed')[0]['evidence'] == 'inference'


def test_inference_is_never_exposed_as_confirmed_fact(tmp_path):
    memory = Memory(tmp_path / 'memory.sqlite')
    memory.add('summary', 'probably lives in Bishkek', 'model')
    memory.add('preference', 'likes short answers', 'user')
    memory.add('project', 'Bishkek project', 'user', evidence='confirmed')
    assert {row['evidence'] for row in memory.search('Bishkek answers')} == {'inference', 'preference', 'confirmed'}


def test_retention_and_row_limit_do_not_remove_calendar(tmp_path):
    memory = Memory(tmp_path / 'memory.sqlite', max_rows=3, retention_days=30)
    for index in range(5):
        memory.add('dialogue', f'entry {index}', 'user')
    assert len(memory.items()) == 3
    with memory.connect() as db:
        db.execute("UPDATE memories SET updated='2000-01-01T00:00:00+00:00'")
        db.execute("INSERT INTO events(title,start,timezone) VALUES('event','2000-01-01','UTC')")
    memory.prune()
    assert memory.items() == []
    with memory.connect() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1
