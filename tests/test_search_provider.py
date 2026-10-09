from dataclasses import replace
import pytest
from eidos.agent.settings import AgentSettings
from eidos.agent.harness import TaskContext
from eidos.agent.memory import Memory
from eidos.agent.tools import build_registry


def test_search_api_sources_without_leaking_key(tmp_path, monkeypatch):
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.get',lambda self,name:'test-api-key')
    seen = []
    def request(method, url, **kwargs):
        assert method=='GET' and kwargs['headers']['X-Subscription-Token']=='test-api-key'
        assert 'test-api-key' not in url
        seen.append(url)
        return {'web':{'results':[{'title':'Python','url':'https://python.org','description':'Official site'}]}}
    monkeypatch.setattr('eidos.agent.providers.request_json',request)
    registry=build_registry(AgentSettings(search_provider='brave'),Memory(tmp_path/'memory.sqlite'))
    context=TaskContext()
    result=registry.execute('web_search',{'query':'Python'},context)
    assert result.verified and 'https://python.org' in result.text and 'test-api-key' not in result.text
    assert context.untrusted_data and len(seen)==1


def test_search_api_missing_key_and_remote_access(tmp_path, monkeypatch):
    monkeypatch.setattr('eidos.agent.secrets.SecretStore.get',lambda self,name:None)
    registry=build_registry(AgentSettings(search_provider='brave'),Memory(tmp_path/'memory.sqlite'))
    with pytest.raises(ValueError,match='API key'):
        registry.execute('web_search',{'query':'Python'},TaskContext())
    with pytest.raises(PermissionError):
        registry.execute('web_search',{'query':'Python'},TaskContext(origin='telegram'))
