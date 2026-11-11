"""Local synthetic Russian STT comparison; never executes recognized commands."""
import argparse
from dataclasses import replace
import gc
import json
from pathlib import Path
import re
import sys
from threading import Event, Thread
import time
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import psutil
from huggingface_hub.constants import HF_HUB_CACHE
from eidos.core.config import AppConfig
from eidos.core.metrics import StageMetrics, METRICS
from eidos.modules.voice.recorder import resample
from eidos.modules.voice.stt import WhisperSTT, VoskSTT
from eidos.modules.voice import stt as voice_stt
from eidos.modules.voice.tts import SapiTTS
from eidos.agent.harness import deterministic_call

PHRASES = ['Открой блокнот', 'Сделай громкость тридцать процентов', 'Прочитай перевод',
           'Который час', 'Да да повтори повтори', 'Переведи область экрана']


def words(text):
    return re.findall(r'\w+', text.lower().replace('ё', 'е'))


def word_errors(reference, hypothesis):
    left, right = words(reference), words(hypothesis)
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (a != b)))
        previous = current
    return previous[-1], len(left)


def load_audio(path):
    with wave.open(str(path), 'rb') as source:
        if source.getsampwidth() != 2 or source.getnchannels() != 1:
            raise ValueError('Expected mono PCM16 WAV')
        audio = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').astype(np.float32) / 32768.
        return resample(audio, source.getframerate())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('docs/audit-2026-10-13/voice-stage-comparison.json'))
    parser.add_argument('--vosk-model', type=Path, default=Path('.cache/voice-models/vosk-model-small-ru-0.22'))
    parser.add_argument('--whisper-cache', type=Path, default=Path(HF_HUB_CACHE))
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--baseline', action='store_true', help='Measure tracked pre-modernization Whisper without modifying checkout')
    args = parser.parse_args()
    root = ROOT / '.cache' / 'modernization-corpus'
    root.mkdir(parents=True, exist_ok=True)
    report = {'source': 'Windows SAPI synthetic Russian; no microphone capture; no commands executed',
              'limitations': 'WER from six synthetic phrases is not representative of live microphone accuracy.',
              'cpu_count': psutil.cpu_count(), 'ram_total_gib': round(psutil.virtual_memory().total / 2**30, 2),
              'engines': {}}
    cases = []
    for index, reference in enumerate(PHRASES):
        path = root / f'{index}.wav'
        if not path.is_file():
            temporary = SapiTTS().synthesize(reference, '', Event())
            temporary.replace(path)
        clean = load_audio(path)
        cases.append((reference, 'clean', clean))
        noise = np.random.default_rng(index).normal(0, .008, clean.size).astype(np.float32)
        cases.append((reference, 'noise', clean + noise))
    constructors = {'whisper': WhisperSTT, 'vosk': VoskSTT}
    if args.baseline:
        import subprocess
        code = subprocess.check_output(['git', 'show', 'HEAD:eidos/modules/voice/stt.py'], cwd=ROOT).decode('utf-8')
        namespace = {'__name__': 'eidos.modules.voice.baseline_stt', '__package__': 'eidos.modules.voice'}
        exec(compile(code, 'tracked-baseline-stt.py', 'exec'), namespace)
        constructors = {'whisper_before': namespace['WhisperSTT']}
    for name, constructor in constructors.items():
        config = replace(AppConfig(), speak=False, stt_engine='vosk' if name == 'vosk' else 'whisper',
                         vosk_model_path=str(args.vosk_model.resolve()))
        engine, metrics = constructor(), StageMetrics()
        voice_stt.METRICS = StageMetrics()
        rows, samples = [], []
        stop = Event()
        process = psutil.Process()
        def sample():
            while not stop.wait(.02):
                samples.append(process.memory_info().rss)
        monitor = Thread(target=sample, daemon=True)
        monitor.start()
        started_cpu, started_wall = time.process_time(), time.perf_counter()
        try:
            for repeat in range(args.repeats):
                for index, (reference, condition, audio) in enumerate(cases):
                    started = time.perf_counter()
                    error = ''
                    try:
                        text = engine.transcribe(audio, config, args.whisper_cache, lambda *a: None, Event())
                    except Exception as exc:
                        text, error = '', type(exc).__name__
                    milliseconds = (time.perf_counter() - started) * 1000
                    metrics.observe('stt', milliseconds, cold=repeat == 0 and index == 0)
                    count, total = word_errors(reference, text)
                    rows.append(dict(reference=reference, condition=condition, repeat=repeat,
                        transcript=text, error=error, ms=round(milliseconds, 3), word_errors=count,
                        reference_words=total, exact=words(reference) == words(text)))
                    print(f'{name} {repeat}/{index}: {milliseconds:.1f} ms, errors {count}/{total}', flush=True)
            for _ in range(500):
                with metrics.measure('command_routing'):
                    deterministic_call('Открой блокнот')
            stages = metrics.snapshot()
            stages['model_load'] = voice_stt.METRICS.snapshot()['model_load']
            report['engines'][name] = dict(stages=stages, cases=rows,
                wer=sum(row['word_errors'] for row in rows) / sum(row['reference_words'] for row in rows),
                exact_rate=sum(row['exact'] for row in rows) / len(rows),
                errors=sum(bool(row['error']) for row in rows), peak_rss_mib=round(max(samples or [process.memory_info().rss]) / 2**20, 2),
                cpu_percent_one_core=round(100 * (time.process_time() - started_cpu) / (time.perf_counter() - started_wall), 2))
        finally:
            stop.set()
            monitor.join()
            del engine
            gc.collect()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
