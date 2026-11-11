from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest
from eidos.agent.harness import TaskContext, deterministic_call
from eidos.agent.memory import Memory
from eidos.agent.settings import AgentSettings
from eidos.desktop.intents import parse, navigation_url, search_url
from eidos.desktop.commands import DesktopCommands
from eidos.desktop.session import SessionStore
from eidos.desktop.tasks import Tasks


@pytest.mark.parametrize('phrase,expected', [
    ('Установи громкость на 40 процентов', ('volume', {'mode': 'set', 'value': 40})),
    ('Прибавь громкость на десять процентов', ('volume', {'mode': 'up', 'value': 10})),
    ('Убавь звук на двадцать пять процентов', ('volume', {'mode': 'down', 'value': 25})),
    ('Прибавь звук', ('volume', {'mode': 'up', 'value': 10})),
    ('Мут', ('mute', {'enabled': True})),
    ('Сфотографируй экран', ('screenshot', {'mode': 'primary'})),
    ('Сделай скриншот всех экранов', ('screenshot', {'mode': 'all'})),
    ('Сделай скриншот области', ('screenshot', {'mode': 'region'})),
])
def test_local_intents(phrase, expected):
    assert parse(phrase) == expected
    if expected[0] in ('volume', 'mute'): assert deterministic_call(phrase) == expected


@pytest.mark.parametrize('phrase', ['Не выключай компьютер', 'Как выключить компьютер?',
    'Не перезагружай компьютер', 'Не делай скриншот', 'Как открыть Steam?'])
def test_negations_and_questions_are_not_actions(phrase):
    assert parse(phrase)[0] == 'refuse'


@pytest.mark.parametrize('value', ['file:///C:/secret', 'javascript:alert(1)', 'https://user:password@example.com',
    'http://', 'example.com & shutdown', 'https://example.com:9999', 'https://example.com\\evil'])
def test_bad_navigation_urls(value):
    with pytest.raises(ValueError): navigation_url(value)


def test_search_is_url_encoded_and_google_is_default():
    value = search_url('C++ & x=1 # тест', AgentSettings().search_provider)
    assert urlsplit(value).hostname == 'www.google.com'
    assert parse_qs(urlsplit(value).query)['q'] == ['C++ & x=1 # тест']
    assert navigation_url('example.com') == 'https://example.com'
    assert parse('Установи громкость на -20 процентов')[0] == 'refuse'
    assert parse('Установи громкость на 40.5 процентов')[0] == 'refuse'


class Backend:
    def __init__(self): self.calls, self.rows = [], []
    def windows(self): return self.rows
    def launch(self, value): self.calls.append(('launch', value))
    def power(self, action): self.calls.append(('power', action))
    def activate(self, value): self.calls.append(('activate', value)); return True


def test_power_is_bound_to_current_action_expires_and_saves_before_execution(tmp_path):
    backend, clock = Backend(), [10.]
    commands = DesktopCommands(AgentSettings(), Memory(tmp_path / 'memory.sqlite'), tmp_path,
        backend=backend, clock=lambda: clock[0])
    commands.ui = lambda *args: ''
    context = TaskContext()
    commands.handle('Выключи компьютер', context)
    assert backend.calls == []
    commands.handle('Подтверждаю перезагрузку', context)
    assert backend.calls == []
    commands.handle('Подтверждаю выключение', context)
    assert backend.calls == [('power', 'shutdown')]
    assert commands.sessions.path.is_file()
    commands.handle('Подтверждаю выключение', context)
    assert len(backend.calls) == 1
    commands.handle('Перезагрузи компьютер', context)
    clock[0] += 15
    commands.handle('Подтверждаю перезагрузку', context)
    assert len(backend.calls) == 1
    commands.handle('Выключи компьютер', context)
    commands.handle('Отмена', context)
    commands.handle('Подтверждаю выключение', context)
    assert len(backend.calls) == 1


def test_restore_deduplicates_skips_running_and_continues_after_missing(tmp_path):
    a, b = tmp_path / 'a.exe', tmp_path / 'b.exe'
    a.touch(); b.touch()
    backend = Backend()
    backend.rows = [{'name': 'a', 'path': str(a), 'hwnd': 1}, {'name': 'a', 'path': str(a), 'hwnd': 2}]
    store = SessionStore(tmp_path / 'session.json', backend)
    assert store.save() == 1
    data = json.loads(store.path.read_text(encoding='utf-8'))
    assert data['version'] == 1 and set(data['applications'][0]) == {'name', 'path'}
    data['applications'] += [{'name': 'missing', 'path': str(tmp_path / 'missing.exe')},
        {'name': 'b', 'path': str(b), 'arguments': '--private-token'}, {'name': 'b', 'path': str(b)}]
    store.path.write_text(json.dumps(data), encoding='utf-8')
    result = store.restore(TaskContext())
    assert backend.calls == [('launch', str(b.resolve()))]
    assert 'Не найдено: 1' in result and 'Уже открыто: 1' in result
    assert not list(tmp_path.glob('.session-*.json'))


def test_real_local_tasks_and_persistent_external_cache(tmp_path):
    memory = Memory(tmp_path / 'memory.sqlite')
    tasks = Tasks(memory)
    zone = 'Asia/Bishkek'
    assert tasks.today(zone) == 'На сегодня задач нет.'
    tasks.add('Реальная задача', zone)
    assert 'Реальная задача' in tasks.today(zone)
    day = datetime.now(ZoneInfo(zone)).date()
    provider = SimpleNamespace(name='configured-provider', connected=True, fetch=lambda: [
        {'title': 'Просроченная', 'due': (day - timedelta(days=1)).isoformat(), 'completed': False},
        {'title': 'Сегодня', 'due': day.isoformat(), 'completed': False},
        {'title': 'Завершённая', 'due': day.isoformat(), 'completed': True}])
    tasks.connect_provider(provider)
    result = tasks.today(zone)
    assert 'Просроченная' in result and 'Завершённая' not in result
    restarted = Tasks(memory)
    def offline(): raise ConnectionError()
    provider.fetch = offline
    restarted.connect_provider(provider)
    assert 'Сохранённые данные' in restarted.today(zone)
    provider.connected = False
    assert restarted.today(zone) == 'Источник задач не подключён.'


def test_session_uses_verified_app_launcher_instead_of_helper_process(tmp_path):
    launcher, helper = tmp_path / 'steam.exe', tmp_path / 'steamwebhelper.exe'
    launcher.touch(); helper.touch()
    backend = Backend()
    backend.rows = [{'path': str(helper), 'launch_path': str(launcher)}, {'path': str(launcher)}]
    store = SessionStore(tmp_path / 'session.json', backend)
    assert store.save() == 1
    entry = json.loads(store.path.read_text(encoding='utf-8'))['applications'][0]
    assert entry['path'] == str(launcher.resolve())
    store.restore(TaskContext())
    assert backend.calls == []


def test_no_pending_power_when_gui_prompt_cannot_be_shown(tmp_path):
    backend = Backend()
    commands = DesktopCommands(AgentSettings(), Memory(tmp_path / 'memory.sqlite'), tmp_path, backend=backend)
    with pytest.raises(RuntimeError): commands.handle('Выключи компьютер', TaskContext())
    assert commands.pending is None and backend.calls == []
