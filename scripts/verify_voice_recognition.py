"""Local Whisper checks on SAPI generated phrases. Never executes a tool."""
import json
from pathlib import Path
import sys
from threading import Event
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
from eidos.core.config import AppConfig, data_dir
from eidos.modules.voice.intents import strip_wake_prefix
from eidos.modules.voice.recorder import resample
from eidos.modules.voice.stt import WhisperSTT
from eidos.modules.voice.tts import SapiTTS
from eidos.agent.harness import deterministic_call

output = Path('docs/screenshots/voice-upgrade/recognition-report.json')
cache = data_dir() / 'models'
report = {'source': 'Синтетические фразы Windows SAPI, не запись микрофона',
          'tools_executed': False, 'cases': {}}


def synthesize(text):
    path = SapiTTS().synthesize(text, '', Event())
    try:
        with wave.open(str(path), 'rb') as source:
            audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16).astype(np.float32) / 32768.
            return resample(audio, source.getframerate())
    finally:
        path.unlink(missing_ok=True)


def save():
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


try:
    if not list(cache.glob('models--Systran--faster-whisper-base/snapshots/*/model.bin')):
        raise RuntimeError('Локальная модель base не найдена. Новая модель не загружалась.')
    stt = WhisperSTT()
    config = AppConfig(speak=False)
    clean = synthesize('Эйдос, открой Ютуб.')
    repeated = synthesize('Да да. Повтори повтори.')
    cases = {'clean_wake_command': clean,
             'controlled_noise': clean + np.random.default_rng(42).normal(0, .012, clean.size).astype(np.float32),
             'repeated_words': repeated,
             'silence': np.zeros(16000, dtype=np.float32)}
    for name, audio in cases.items():
        try:
            text = stt.transcribe(audio, config, cache, lambda state, message: print(message, flush=True), Event())
            command = strip_wake_prefix(text)
            report['cases'][name] = {'transcript': text, 'command': command,
                                     'deterministic_intent': deterministic_call(command)}
        except Exception as exc:
            report['cases'][name] = {'rejected': str(exc)}
        save()
except Exception as exc:
    report['unavailable'] = str(exc)
    save()
