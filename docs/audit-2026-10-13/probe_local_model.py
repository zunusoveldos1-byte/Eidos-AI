"""Local synthetic prompts only; does not execute tool calls or load user memory."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eidos.agent.settings import AgentSettings
from eidos.agent.providers import OllamaProvider, request_json
from eidos.agent.harness import TaskContext, Tool, ToolResult

evidence = json.loads((Path(__file__).parent / 'evidence.json').read_text(encoding='utf-8'))
saved = evidence['runtime']['agent']
settings = AgentSettings(model=saved['model'], context_size=saved['context_size'])
provider = OllamaProvider(settings)
results = []
tool = Tool('calendar_list', 'View a synthetic calendar. No side effects.', {},
            lambda a, c: ToolResult('[]'), 'calendar.read')
for prompt, tools in [('Поздоровайся на русском одной короткой фразой.', []),
                      ('Покажи календарь: вызови calendar_list.', [tool.schema()])]:
    started = time.monotonic()
    response = provider.chat([{'role': 'user', 'content': prompt}], tools, TaskContext(timeout=60))
    results.append({'synthetic_prompt': prompt, 'response': response,
                    'seconds': round(time.monotonic() - started, 3), 'metrics': provider.metrics})
result = {'model': settings.model, 'context_size': settings.context_size, 'runs': results,
          'running_models_after': request_json('GET', settings.ollama_url + '/api/ps'),
          'tool_calls_executed': False, 'user_profile_or_memory_sent': False}
(Path(__file__).parent / 'local-model-probe.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
