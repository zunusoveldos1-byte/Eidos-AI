import pytest
from PyQt6.QtCore import QRectF
from eidos.agent.harness import TaskContext
from eidos.agent.settings import AgentSettings
from eidos.agent.tools import build_registry
from eidos.agent.memory import Memory
from eidos.modules.ocr.engine import TextLine


def test_screen_tool_requires_explicit_local_input(tmp_path):
    registry = build_registry(AgentSettings(), Memory(tmp_path / 'memory.sqlite'))
    with pytest.raises(ValueError, match='область'):
        registry.execute('screen_read_text', {}, TaskContext())
    with pytest.raises(PermissionError):
        registry.execute('screen_read_text', {}, TaskContext(origin='telegram', permissions=frozenset({'screen.read'}), screen_text='private'))
    result = registry.execute('screen_read_text', {}, TaskContext(screen_text='Selected words'))
    assert 'Selected words' in result.text


def test_translation_uses_registry_and_supplied_image():
    from eidos.agent.screen import screen_registry
    marker = object()
    class OCR:
        def recognize(self, image, source):
            assert image is marker
            return [TextLine('Hello', QRectF(0, 0, 20, 10))]
    class Translator:
        def translate(self, text, source, target):
            return 'Привет'
    registry = screen_registry(OCR(), Translator())
    result = registry.execute('screen_translate', {'source': 'en', 'target': 'ru', 'provider': 'google'}, TaskContext(screen_image=marker))
    assert result.data[0].translation == 'Привет'
    assert 'Привет' in result.text
