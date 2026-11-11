import asyncio
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
import pytest
from eidos.agent.settings import AgentSettings, SettingsStore
from eidos.agent.harness import TaskContext, Harness, Registry, Tool, ToolResult


def settings(): return replace(AgentSettings(), provider='gemini')
def secrets(): return SimpleNamespace(get=lambda name: 'unit-gemini-key')


def test_gemini_settings_and_vault_name(tmp_path):
    from eidos.agent.secrets import SecretStore
    store = SettingsStore(tmp_path/'agent.json')
    store.save(settings())
    assert store.load().gemini_model == 'gemini-2.5-flash'
    assert 'gemini' in SecretStore.NAMES
    with pytest.raises(ValueError): replace(settings(), gemini_model='../bad?key=secret').validate()


def test_system_history_tools_and_signatures_round_trip(monkeypatch):
    from eidos.agent.gemini import GeminiProvider
    provider = GeminiProvider(settings(), secrets())
    bodies = []
    parts = [{'functionCall': {'name':'calendar_list','args':{}}, 'thoughtSignature':'opaque-signature'}]
    async def request(method, suffix, context, body=None):
        bodies.append(body)
        return {'candidates':[{'content':{'role':'model','parts':parts if len(bodies)==1 else [{'text':'Готово'}]},'finishReason':'STOP'}]}
    monkeypatch.setattr(provider, '_request', request)
    messages = [{'role':'system','content':'system'}, {'role':'user','content':'earlier'},
                {'role':'assistant','content':'history'}, {'role':'user','content':'calendar'}]
    tools = [{'type':'function','function':{'name':'calendar_list','description':'calendar',
              'parameters':{'type':'object','properties':{},'additionalProperties':False}}}]
    response = provider.chat(messages,tools,TaskContext())
    assert response['tool_calls'][0]['function'] == {'name':'calendar_list','arguments':{}}
    messages += [response, {'role':'tool','tool_name':'calendar_list','tool_call_id':response['tool_calls'][0]['id'],'content':'empty'}]
    assert provider.chat(messages,tools,TaskContext())['content']=='Готово'
    assert bodies[0]['systemInstruction']['parts']==[{'text':'system'}]
    assert bodies[0]['contents'][1]['role']=='model'
    assert bodies[0]['tools'][0]['functionDeclarations'][0]['parametersJsonSchema']['additionalProperties'] is False
    assert bodies[1]['contents'][-2]['parts']==parts
    assert bodies[1]['contents'][-1]['parts'][0]['functionResponse']['response']=={'result':'empty'}


def test_missing_key_and_secret_payload_never_reach_network(monkeypatch):
    from eidos.agent.gemini import GeminiProvider
    for vault, text, match in [(SimpleNamespace(get=lambda n:None),'hello','ключ'),
                               (secrets(),'unit-gemini-key','секрет')]:
        provider=GeminiProvider(settings(),vault)
        monkeypatch.setattr(provider,'_request',lambda *a,**kw:pytest.fail('Unexpected network'))
        with pytest.raises(ValueError,match=match): provider.chat([{'role':'user','content':text}],[],TaskContext())


def test_function_call_runs_through_existing_harness(monkeypatch):
    from eidos.agent.gemini import GeminiProvider
    from eidos.agent.providers import provider_for
    provider=provider_for(settings(),secrets())
    assert isinstance(provider,GeminiProvider)
    n=[0]
    async def request(*args,**kwargs):
        n[0]+=1
        return {'candidates':[{'content':{'parts':[{'functionCall':{'name':'calendar_list','args':{}}}] if n[0]==1 else [{'text':'Проверено'}]},'finishReason':'STOP'}]}
    monkeypatch.setattr(provider,'_request',request)
    invoked=[]
    registry=Registry()
    registry.add(Tool('calendar_list','calendar',{},lambda args,ctx:invoked.append(True) or ToolResult('Задач нет'), 'calendar.read',safe_retry=True))
    answer=Harness(registry,provider).run('Посмотри список моих встреч',TaskContext())
    assert invoked==[True] and 'Задач нет' in answer


@pytest.mark.parametrize('status',[400,403,404,429,503])
def test_http_errors_never_expose_key_or_vendor_payload(monkeypatch,status):
    import httpx
    from eidos.agent.gemini import GeminiProvider
    provider=GeminiProvider(settings(),secrets())
    original=httpx.AsyncClient
    requests=[]
    def receive(request):
        requests.append(request)
        return httpx.Response(status,json={'error':{'message':'unit-gemini-key'}})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(receive),**kw))
    with pytest.raises(RuntimeError) as error:
        provider.chat([{'role':'user','content':'Hello'}],[],TaskContext())
    assert str(status) in str(error.value) and 'unit-gemini-key' not in str(error.value)
    assert 'unit-gemini-key' not in str(requests[0].url)
    assert requests[0].headers['x-goog-api-key']=='unit-gemini-key'


def test_cancel_before_headers_interrupts_async_transport(monkeypatch):
    import httpx
    from eidos.agent.gemini import GeminiProvider
    original=httpx.AsyncClient
    cancel=Event()
    cleanup=[]
    async def receive(request):
        try:
            cancel.set()
            await asyncio.sleep(100)
            return httpx.Response(200,json={})
        finally: cleanup.append(True)
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(receive),**kw))
    with pytest.raises(InterruptedError):
        GeminiProvider(settings(),secrets()).chat([{'role':'user','content':'Hello'}],[],TaskContext(cancel=cancel))
    assert cleanup==[True]


def test_key_check_uses_model_metadata_without_generation(monkeypatch):
    import httpx
    from eidos.agent.gemini import GeminiProvider
    original=httpx.AsyncClient
    def receive(request):
        assert request.method=='GET' and request.url.path.endswith('/models/gemini-2.5-flash')
        return httpx.Response(200,json={'supportedGenerationMethods':['generateContent']})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(receive),**kw))
    assert 'ключ принят' in GeminiProvider(settings(),secrets()).check_connection(TaskContext())
