import threading

import pytest

from eidos.agent.harness import TaskContext
from eidos.agent.screen import screen_registry
from eidos.modules.ocr.engine import OnlineTranslator, TextLine
from eidos.modules.ocr.interface import JonSnowTranslator
from eidos.modules.voice.tts import EdgeTTS
from PyQt6.QtCore import QRectF


def test_translation_rejects_secrets_before_any_network_request(monkeypatch):
    calls = []
    monkeypatch.setattr('eidos.modules.ocr.engine.urlopen', lambda *a, **k: calls.append(a))
    with pytest.raises(ValueError, match='секрет'):
        OnlineTranslator().translate('password=unit-test-secret', 'ru', 'en')
    assert calls == []


def test_screen_checks_entire_ocr_before_sending_first_line():
    calls = []
    class OCR:
        def recognize(self, *args):
            return [TextLine('ordinary text', QRectF()), TextLine('token=unit-test-secret', QRectF())]
    class Translator:
        def translate(self, *args):
            calls.append(args)
            return 'translated'
    with pytest.raises(ValueError, match='секрет'):
        JonSnowTranslator(OCR(), Translator()).process(None, 'ru', 'en', 'google', threading.Event())
    assert calls == []


def test_network_text_tool_checks_exact_known_secret():
    class Translator:
        def translate(self, *args):
            pytest.fail('secret reached translator')
    context = TaskContext(secret_values=('fictional-credential',))
    with pytest.raises(ValueError, match='секрет'):
        screen_registry(translator=Translator()).execute('text_translate',
            dict(text='fictional-credential', source='ru', target='en', provider='google'), context)


def test_ocr_only_is_available_without_external_provider():
    class OCR:
        def recognize(self, *args):
            return [TextLine('локальный текст', QRectF())]
    class Translator:
        def translate(self, *args):
            pytest.fail('OCR-only used network')
    lines = JonSnowTranslator(OCR(), Translator()).process(None, 'ru', 'en', '', threading.Event())
    assert lines[0].text == 'локальный текст'
    assert lines[0].translation == ''


def test_edge_tts_rejects_secret_before_creating_file(monkeypatch):
    monkeypatch.setattr('eidos.modules.voice.tts.EdgeTTS._collect', lambda *a, **k: pytest.fail('secret reached file'))
    with pytest.raises(ValueError, match='секрет'):
        EdgeTTS().synthesize('password=unit-test-secret', 'voice', threading.Event())


def test_external_provider_rejects_secret_in_history_before_http(monkeypatch):
    from eidos.agent.providers import OpenAIProvider
    from eidos.agent.settings import AgentSettings
    class Secrets:
        def get(self, name): return 'fictional-api-credential'
    monkeypatch.setattr('eidos.agent.providers.request_json', lambda *a, **k: pytest.fail('secret sent via HTTP'))
    with pytest.raises(ValueError, match='секрет'):
        OpenAIProvider(AgentSettings(provider='openai'), Secrets()).chat(
            [{'role': 'user', 'content': 'ordinary'}, {'role': 'tool', 'content': 'password=unit-test-secret'}], [], TaskContext())


def test_browser_tool_rejects_secret_before_confirmation_or_execution():
    from eidos.agent.harness import Registry, Tool, ToolResult
    registry = Registry()
    registry.add(Tool('web_search', 'Search', {'query': {'type': 'string'}},
        lambda args, context: pytest.fail('secret reached tool'), 'browser.read'))
    with pytest.raises(ValueError, match='секрет'):
        registry.execute('web_search', {'query': 'password=unit-test-secret'}, TaskContext())
