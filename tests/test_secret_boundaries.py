from eidos.agent.harness import Registry, TaskContext, Tool, ToolResult
from eidos.agent.memory import Memory
from eidos.agent.service import AgentService


def test_vault_value_without_recognizable_token_format_is_not_saved(tmp_path, monkeypatch):
    secret = 'opaque-example-vault-value'
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.values', lambda self: (secret,))
    service = AgentService(tmp_path)
    service.settings.memory_enabled = True
    assert service.memory.add('preference', 'Значение ' + secret, 'user') is None
    answer = service.respond('Используй ' + secret, TaskContext())
    assert 'секрет' in answer and secret not in answer
    assert not service.memory.items()
    assert not service.history


def test_known_credentials_are_redacted_before_tool_result_reaches_model():
    registry = Registry()
    registry.add(Tool('read', 'Read', {}, lambda a,c: ToolResult('key is opaque-vault-value'),
                      'documents.read', safe_retry=True))
    context = TaskContext(secret_values=('opaque-vault-value',))
    result = registry.execute('read', {}, context)
    assert result.verified and 'opaque-vault-value' not in result.text
    assert 'секрет скрыт' in result.text
