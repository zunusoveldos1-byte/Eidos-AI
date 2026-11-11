"""Synthetic local TTS/LLM/streaming measurements; never accesses user state."""
from dataclasses import replace
import json
from pathlib import Path
import sys
from threading import Event
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import httpx
from eidos.agent.harness import TaskContext
from eidos.agent.providers import OllamaProvider
from eidos.agent.settings import AgentSettings
from eidos.core.config import AppConfig
from eidos.core.metrics import StageMetrics
from eidos.modules.voice import stt
from eidos.modules.voice.tts import SapiTTS
from benchmark_voice_stages import load_audio, PHRASES


def main():
    metrics = StageMetrics()
    report = {'source': 'Synthetic phrases; local SAPI, local Ollama, local Vosk; no user history/keys',
              'unmeasured': ['wake_detection: Porcupine key/model not supplied',
                             'audio_buffering: live microphone not activated'], 'errors': []}
    for index, phrase in enumerate(PHRASES):
        try:
            with metrics.measure('tts', cold=index == 0):
                path = SapiTTS().synthesize(phrase, '', Event())
            if path:
                path.unlink(missing_ok=True)
        except Exception as exc:
            report['errors'].append('tts:' + type(exc).__name__)
    settings = AgentSettings()
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            tags = client.get(settings.ollama_url + '/api/tags').json()
            loaded = client.get(settings.ollama_url + '/api/ps').json()
        report['llm_model'] = settings.model
        report['llm_initially_loaded'] = any(m.get('name') == settings.model for m in loaded.get('models', []))
        if any(m.get('name') == settings.model for m in tags.get('models', [])):
            from eidos.agent import providers
            from eidos.core import metrics as global_metrics
            old_metrics = global_metrics.METRICS
            global_metrics.METRICS = metrics
            try:
                provider = OllamaProvider(settings)
                for index in range(3):
                    provider.chat([{'role': 'user', 'content': 'Ответь одним словом: привет.'}], [], TaskContext(timeout=50))
                    print('local LLM request', index + 1, flush=True)
                report['llm_last_native_metrics'] = provider.metrics
            finally:
                global_metrics.METRICS = old_metrics
        else:
            report['errors'].append('llm:model_not_installed')
    except Exception as exc:
        report['errors'].append('llm:' + type(exc).__name__)
    model = ROOT / '.cache/voice-models/vosk-model-small-ru-0.22'
    if model.is_dir():
        config = replace(AppConfig(), stt_engine='vosk', vosk_model_path=str(model))
        engine = stt.VoskSTT()
        stt.METRICS = metrics
        for index in range(6):
            audio = load_audio(ROOT / f'.cache/modernization-corpus/{index}.wav')
            cancel = Event()
            engine.begin_stream(config, ROOT / '.cache', lambda *args: None, cancel)
            for offset in range(0, len(audio), 320):
                engine.feed(audio[offset:offset + 320], cancel)
            with metrics.measure('stt_finalization'):
                engine.finish_stream(cancel)
    report['stages'] = metrics.snapshot()
    output = ROOT / 'docs/audit-2026-10-13/local-response-stages.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
