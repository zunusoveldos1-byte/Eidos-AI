import threading
from pathlib import Path

import pytest

from eidos.agent.harness import Harness, Registry, Tool, TaskContext, ToolResult
from eidos.agent.memory import Memory
from eidos.agent.settings import AgentSettings, SettingsStore


class FakeProvider:
    def __init__(self, *responses):
        self.responses = iter(responses)

    def chat(self, messages, tools, context):
        return next(self.responses)


def call(name, **arguments):
    return {'role': 'assistant', 'content': '', 'tool_calls': [
        {'function': {'name': name, 'arguments': arguments}}]}


def registry(callback, *, confirmation=False, safe_retry=False):
    result = Registry()
    result.add(Tool('test', 'Test', {'value': {'type': 'integer', 'minimum': 0, 'maximum': 100}},
                    callback, permission='windows.audio', confirmation=confirmation, safe_retry=safe_retry))
    return result


def test_arguments_checked_before_side_effect():
    seen = []
    reg = registry(lambda args, ctx: seen.append(args) or ToolResult('ok'))
    for args in ({'value': True}, {'value': 101}, {'value': 2, 'code': 'danger'}, {}):
        with pytest.raises(ValueError):
            reg.execute('test', args, TaskContext())
    assert not seen


def test_remote_permission_and_confirmation_cannot_be_model_granted():
    seen = []
    reg = registry(lambda args, ctx: seen.append(args) or ToolResult('ok'), confirmation=True)
    with pytest.raises(PermissionError):
        reg.execute('test', {'value': 1}, TaskContext(origin='telegram'))
    with pytest.raises(PermissionError):
        reg.execute('test', {'value': 1}, TaskContext(confirm=lambda action: False))
    assert not seen
    ctx = TaskContext(origin='telegram', permissions=frozenset({'windows.audio'}), confirm=lambda action: True)
    assert reg.execute('test', {'value': 1}, ctx).verified


def test_retry_does_not_repeat_send_and_unsafe_call():
    attempts = []
    def failing(args, ctx):
        attempts.append(1)
        raise ConnectionError('unknown delivery')
    with pytest.raises(ConnectionError):
        registry(failing).execute('test', {'value': 1}, TaskContext())
    assert len(attempts) == 1


def test_cancel_and_max_steps_and_unverified_result():
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(InterruptedError):
        Harness(Registry(), FakeProvider()).run('hi', TaskContext(cancel=cancelled))
    reg = registry(lambda a, c: ToolResult('not verified', verified=False))
    provider = FakeProvider(call('test', value=1), {'content': 'Успешно!'})
    result = Harness(reg, provider).run('hi', TaskContext())
    assert 'не подтверждён' in result.lower()
    endless = FakeProvider(*(call('test', value=1) for _ in range(5)))
    result = Harness(registry(lambda a, c: ToolResult('ok'), safe_retry=True), endless, max_steps=2).run('hi', TaskContext())
    assert 'шагов' in result


def test_memory_persistence_fts_edit_delete_and_secret_filter(tmp_path):
    path = tmp_path / 'memory.sqlite'
    memory = Memory(path)
    ident = memory.add('project', 'Eidos использует Python', 'Пользователь')
    assert Memory(path).search('Python')[0]['id'] == ident
    memory.edit(ident, 'Eidos использует SQLite', 'Пользователь: исправление')
    assert not memory.search('Python')
    assert memory.search('SQLite')
    memory.add('dialogue', 'password=supersecret', 'user')
    assert not memory.search('supersecret')
    memory.delete(ident)
    assert not Memory(path).items()


def test_settings_opt_in_remote_disabled_no_tokens(tmp_path):
    store = SettingsStore(tmp_path / 'agent.json')
    settings = store.load()
    assert not settings.memory_enabled and not settings.remote_permissions
    assert not settings.telegram_enabled and not settings.discord_enabled
    store.save(settings)
    assert 'token' not in store.path.read_text()
    with pytest.raises(ValueError):
        AgentSettings(context_size=999999).validate()
