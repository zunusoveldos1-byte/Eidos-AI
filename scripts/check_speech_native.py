"""Synthesize controlled test text in workers; verify Qt reaches EndOfMedia."""
import os
import sys
import time
import json
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import QApplication
from eidos.modules.voice.tts import SapiTTS, EdgeTTS
from eidos.modules.voice.playback import AudioPlayback

app = QApplication([])
player = AudioPlayback()
player.set_volume(20)
report = {}
finished, errors = [], []
player.finished.connect(lambda: finished.append(True))
player.error.connect(errors.append)
with ThreadPoolExecutor(max_workers=1) as pool:
    for name, provider, voice in [('sapi', SapiTTS(), ''), ('edge', EdgeTTS(), 'ru-RU-SvetlanaNeural')]:
        cancel = Event()
        future = pool.submit(provider.synthesize, 'Привет! Я Эйдос.', voice, cancel, rate=0, volume=100)
        deadline = time.monotonic() + 50
        while not future.done() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if not future.done():
            cancel.set()
        try:
            path = future.result(timeout=5)
            if path is None:
                raise RuntimeError('Synthesis cancelled')
            size = path.stat().st_size
            finished.clear()
            errors.clear()
            player.play(path)
            deadline = time.monotonic() + 12
            while not finished and not errors and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            player.stop()
            app.processEvents()
            report[name] = {'synthesized_bytes': size, 'end_of_media': bool(finished),
                            'temporary_file_removed': not path.exists(), 'errors': list(errors)}
        except Exception as exc:
            report[name] = {'error': str(exc)}
        print(name, json.dumps(report[name], ensure_ascii=False), flush=True)
player.dispose()
Path('docs/screenshots/background/speech-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
