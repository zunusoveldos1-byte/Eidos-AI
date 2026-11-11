"""Opt-in Windows smoke: synthetic SAPI speech -> Silero/Vosk -> silent PCM output.
Run from the repository root. Never records the microphone or writes audio.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json, time
from threading import Event
from PyQt6.QtWidgets import QApplication
from eidos.modules.voice.tts import SapiTTS
from eidos.modules.voice.pcm import PCMAudio
from eidos.modules.voice.playback import AudioPlayback
from eidos.modules.voice.vad import SileroVAD
app=QApplication([])
voices=SapiTTS().list_voices()
if not voices: raise RuntimeError('No SAPI voice')
audio=SapiTTS().synthesize('Проверка речи.', '', Event())
assert isinstance(audio,PCMAudio) and audio.data and not audio.data.startswith(b'RIFF')
vad=SileroVAD()
t=time.perf_counter()
for i in range(100): vad(bytes(1024))
vad_ms=(time.perf_counter()-t)*10
from dataclasses import replace
from eidos.core.config import AppConfig
from eidos.modules.voice.stt import VoskSTT
engine=VoskSTT()
config=replace(AppConfig(), stt_engine='vosk', vosk_model_path=str(__import__('pathlib').Path('.cache/voice-models/vosk-model-small-ru-0.22').resolve()))
engine.begin_stream(config, None, lambda *a:None, Event())
probabilities=[]
t=time.perf_counter()
for offset in range(0,len(audio.data),1024):
 frame=audio.data[offset:offset+1024]
 probabilities.append(vad(frame.ljust(1024,b'\0')))
 engine.feed(frame,Event())
text=engine.finish_stream(Event())
recognition_ms=(time.perf_counter()-t)*1000
assert text and max(probabilities)>.5
player=AudioPlayback()
player.set_volume(0)
finished=[]; errors=[]
player.finished.connect(lambda: finished.append(True))
player.error.connect(errors.append)
player.play(PCMAudio(bytes(16000)))
deadline=time.monotonic()+5
while not finished and not errors and time.monotonic()<deadline:
 app.processEvents(); time.sleep(.005)
player.dispose()
result={'sapi_pcm_bytes':len(audio.data),'sample_rate':audio.sample_rate,'channels':audio.channels,'silero_frame_mean_ms':round(vad_ms,3),'native_pcm_finished':bool(finished),'errors':errors,'vosk_text':text,'vosk_whole_phrase_processing_ms':round(recognition_ms,2),'silero_speech_detected':max(probabilities)>.5}
print(json.dumps(result,ensure_ascii=False))
__import__('pathlib').Path('docs/audit-2026-10-13/checks/pcm-native.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
assert finished and not errors
