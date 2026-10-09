"""Real opt-in Ollama probes; saves measurements without hardware IDs."""
import argparse
import json
from pathlib import Path
import threading
import time
from dataclasses import replace

from eidos.agent.hardware import diagnose, ollama_rss_mib
from eidos.agent.harness import TaskContext, Harness
from eidos.agent.memory import Memory
from eidos.agent.providers import OllamaProvider, request_json
from eidos.agent.settings import AgentSettings
from eidos.agent.tools import build_registry


def main():
    import psutil
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:4b-instruct-2507-q4_K_M')
    parser.add_argument('--output', default='docs/agent-benchmark.json')
    args = parser.parse_args()
    settings = AgentSettings(model=args.model)
    provider = OllamaProvider(settings)
    report = {'hardware_before': diagnose(), 'model': args.model, 'context': settings.context_size, 'think': False, 'runs': []}
    stop = threading.Event()
    samples = []
    def measure():
        while not stop.wait(.1):
            samples.append({'rss_mib': ollama_rss_mib(), 'ram_available_gib': round(psutil.virtual_memory().available/2**30,2)})
    monitor = threading.Thread(target=measure, daemon=True)
    monitor.start()
    try:
        memory = Memory(Path('.cache/benchmark/memory.sqlite'))
        registry = build_registry(settings, memory)
        for prompt, tools in [
            ('Поздоровайся на русском языке одной короткой фразой.', []),
            ('Для просмотра локального календаря вызови calendar_list. Не отвечай без инструмента.', [registry.tools['calendar_list'].schema()]),
            ('Объясни в двух предложениях, чем список Python отличается от кортежа.', []),
        ]:
            context = TaskContext(timeout=180)
            started = time.perf_counter()
            answer = provider.chat([{'role':'user','content':prompt}], tools, context)
            verified = None
            if tools:
                calls = answer.get('tool_calls', [])
                verified = bool(calls)
                for call in calls:
                    fn = call['function']
                    assert fn['name']=='calendar_list'
                    registry.execute(fn['name'], fn['arguments'], context)
            entry = {'prompt':prompt,'seconds':round(time.perf_counter()-started,3), 'response':answer, 'tool_verified':verified, 'metrics':provider.metrics.copy()}
            report['runs'].append(entry)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
        report['running_models'] = request_json('GET', settings.ollama_url+'/api/ps')
        context = TaskContext(timeout=180)
        started = time.perf_counter()
        report['harness_calendar'] = Harness(registry, provider).run('Посмотри локальный календарь и сообщи, есть ли события.', context)
        report['harness_seconds'] = round(time.perf_counter()-started,3)
        # Real cancellation uses streamed output; no side effects.
        cancelled = TaskContext(timeout=180)
        timer = threading.Timer(.5, cancelled.cancel.set)
        timer.start()
        started = time.perf_counter()
        try:
            provider.chat([{'role':'user','content':'Напиши длинное подробное учебное объяснение Python на 500 слов.'}], [], cancelled)
            report['cancelled'] = False
        except InterruptedError:
            report['cancelled'] = True
        finally:
            timer.cancel()
        report['cancellation_seconds'] = round(time.perf_counter()-started,3)
    except Exception as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)
        print(report['error'], flush=True)
    finally:
        stop.set()
        monitor.join(timeout=2)
        report['peak_ollama_rss_mib'] = max((s['rss_mib'] for s in samples), default=0)
        report['minimum_available_ram_gib'] = min((s['ram_available_gib'] for s in samples), default=0)
        report['hardware_after'] = diagnose()
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 1 if 'error' in report else 0


if __name__ == '__main__':
    raise SystemExit(main())
