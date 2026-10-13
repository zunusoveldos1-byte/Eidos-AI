"""Verify native Qt decoder pause/resume and installed TTS with benign test text."""
import json
import math
from pathlib import Path
import struct
import sys
import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication
from eidos.modules.voice.playback import AudioPlayback
from eidos.modules.voice.tts import EdgeTTS, SapiTTS

app = QApplication([])
player = AudioPlayback()
player.set_volume(5)
report = {}
output = Path('docs/screenshots/voice-upgrade/native-report.json')
output.parent.mkdir(parents=True, exist_ok=True)
cache = Path('.cache/native-voice-upgrade')
cache.mkdir(parents=True, exist_ok=True)
audio = cache / 'decoder-test.wav'
with wave.open(str(audio), 'wb') as stream:
    stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
    stream.writeframes(b''.join(struct.pack('<h', int(3000 * math.sin(i * math.tau * 220 / 16000))) for i in range(64000)))


def pump_until(predicate, seconds):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    return bool(predicate())


def save():
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


finished, errors, levels = [], [], []
player.finished.connect(lambda: finished.append(True))
player.error.connect(errors.append)
player.level.connect(levels.append)
try:
    player.play(audio)
    advanced = pump_until(lambda: player._player and player._player.position() >= 600, 6)
    if advanced and player.active:
        player.pause()
        position = player._player.position()
        pump_until(lambda: False, .35)
        stable = player._player.position() == position
        retained = audio.exists()
        player.resume()
        continued = pump_until(lambda: player._player.position() > position + 100, 3)
        complete = pump_until(lambda: bool(finished) or bool(errors), 6)
        report['qt_pause_resume'] = {'pause_position_ms': position, 'position_stable': stable,
            'source_retained_on_pause': retained, 'continued_from_position': continued,
            'end_of_media': bool(finished), 'decoded_levels_received': sum(value > 0 for value in levels),
            'temporary_file_removed': not audio.exists(), 'errors': errors[:],
            'audio_levels_available': player.has_audio_levels}
    else:
        report['qt_pause_resume'] = {'advanced': advanced, 'errors': errors[:]}
    player.stop()
    save()
    with ThreadPoolExecutor(max_workers=1) as pool:
        for name, provider, voice in [('sapi', SapiTTS(), ''), ('edge', EdgeTTS(), 'ru-RU-SvetlanaNeural')]:
            cancel = Event()
            future = pool.submit(provider.synthesize, 'Привет! Я Эйдос. Это проверка голоса.', voice, cancel)
            pump_until(future.done, 48)
            if not future.done():
                cancel.set()
            try:
                path = future.result(timeout=5)
                if path is None:
                    raise RuntimeError('Синтез отменён')
                size = path.stat().st_size
                finished.clear(); errors.clear()
                player.play(path)
                pump_until(lambda: bool(finished) or bool(errors), 12)
                player.stop()
                report[name] = {'bytes': size, 'end_of_media': bool(finished),
                                'temporary_file_removed': not path.exists(), 'errors': errors[:]}
            except Exception as exc:
                report[name] = {'error': str(exc)}
            save()
finally:
    player.dispose()
    save()
