"""Python 3.11+: local Vosk -> async Gemini -> async Edge -> in-memory PCM.

Console demonstration, not a Qt GUI event loop. Ctrl+C stops the session.
No tool execution, history upload, automatic model download or credential logs.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from threading import Event
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from eidos.agent.memory import require_public_text
from eidos.modules.voice.speech_text import prepare_speech, split_sentences
from eidos.modules.voice.stt import native_model_path


def listen_once(model, stop, device=None, max_seconds=15):
    """All PortAudio and Vosk work happens in the executor, not asyncio/Qt."""
    import sounddevice as sd
    from vosk import KaldiRecognizer
    recognizer = KaldiRecognizer(model, 16000)
    parts = []
    deadline = time.monotonic() + max_seconds
    with sd.RawInputStream(samplerate=16000, blocksize=320, device=device,
                           dtype='int16', channels=1) as microphone:
        while not stop.is_set() and time.monotonic() < deadline:
            pcm, overflow = microphone.read(320)
            if overflow:
                raise RuntimeError('Audio overflow: discard this utterance')
            if recognizer.AcceptWaveform(bytes(pcm)):
                text = json.loads(recognizer.Result()).get('text', '').strip()
                if text:
                    return text
        if stop.is_set():
            return ''
        parts.append(json.loads(recognizer.FinalResult()).get('text', ''))
    return ' '.join(parts).strip()


async def ask_gemini(client, text, *, model='gemini-2.5-flash', secret_values=()):
    """Client is genai.Client(...).aio; keep it alive across requests."""
    from google.genai import types
    if len(text) > 4000:
        raise ValueError('Question too long')
    require_public_text(text, secret_values)
    async with asyncio.timeout(25):
        response = await client.models.generate_content(
            model=model, contents=text,
            config=types.GenerateContentConfig(
                system_instruction='Ты голосовой помощник. Ответь по-русски, максимум '
                'двумя короткими предложениями. Без Markdown, списков, URL и кода. '
                'Если не знаешь, скажи об этом. Не утверждай, что выполнил действия.',
                max_output_tokens=180, temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0)))
    answer = prepare_speech(response.text or '', brief=True)
    answer = ' '.join(split_sentences(answer)[:2])
    if not answer:
        raise RuntimeError('Gemini returned no speakable answer')
    require_public_text(answer, secret_values)
    return answer


async def play_pcm(audio):
    """Native miniaudio playback; cancellation closes the device, no process/files."""
    import miniaudio
    done = Event()
    def output():
        frames = yield b''
        position = 0
        while position < len(audio.data):
            end = position + frames * 2 * audio.channels
            frames = yield audio.data[position:end]
            position = end
        done.set()
    generator = output()
    next(generator)
    device = await asyncio.to_thread(miniaudio.PlaybackDevice,
        output_format=miniaudio.SampleFormat.SIGNED16, sample_rate=audio.sample_rate,
        nchannels=audio.channels, buffersize_msec=50)
    try:
        await asyncio.to_thread(device.start, generator)
        async with asyncio.timeout(120):
            while not done.is_set():
                await asyncio.sleep(.01)
            await asyncio.sleep(.05)  # drain the final hardware buffer
    finally:
        await asyncio.to_thread(device.close)


async def speak(text, *, voice='ru-RU-SvetlanaNeural', secret_values=()):
    from eidos.modules.voice.tts import EdgeTTS
    require_public_text(text, secret_values)
    if len(text) > 2000:
        raise ValueError('Speech too long')
    cancel = Event()
    engine = EdgeTTS()
    try:
        data = await engine._collect(text, voice, cancel, 10, 100)
        if data:
            audio = await asyncio.to_thread(engine._decode, data)
            await play_pcm(audio)
    finally:
        cancel.set()


async def run(args):
    from google import genai
    from google.genai import types
    from vosk import Model
    path = args.vosk_model.resolve()
    if not (path / 'am/final.mdl').is_file() or not (path / 'conf/model.conf').is_file():
        raise ValueError('Select an unpacked local Vosk model')
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        raise ValueError('Set GEMINI_API_KEY in the launching environment')
    stop = Event()
    print('Loading the local Vosk model once…')
    model = await asyncio.to_thread(Model, native_model_path(path))
    # One turn at a time: bounded to one utterance/answer, no audio backlog.
    async with genai.Client(api_key=key, http_options=types.HttpOptions(timeout=25000)).aio as client:
        try:
            while True:
                print('Listening (15 s maximum). Ctrl+C to stop.')
                text = await asyncio.to_thread(listen_once, model, stop, args.device)
                if not text:
                    continue
                try:
                    started = time.perf_counter()
                    answer = await ask_gemini(client, text, model=args.model, secret_values=(key,))
                    print(f'LLM complete in {time.perf_counter() - started:.2f} s; speaking…')
                    # Capture stream is already closed: no self-listening.
                    await speak(answer, secret_values=(key,))
                except (TimeoutError, ValueError, RuntimeError) as exc:
                    print('Turn failed:', type(exc).__name__, '; retry by speaking again.')
                except Exception as exc:
                    # Vendor exception messages can contain input/credentials.
                    print('Service error:', type(exc).__name__, '; check connectivity, quota and model access.')
        finally:
            stop.set()  # to_thread cancellation alone does not stop native reads.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vosk-model', type=Path, default=ROOT / '.cache/voice-models/vosk-model-small-ru-0.22')
    parser.add_argument('--model', default='gemini-2.5-flash')
    parser.add_argument('--device', type=int, default=None)
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print('Stopped.')
    except Exception as exc:
        print('Startup failed:', type(exc).__name__, str(exc) if isinstance(exc, (ValueError, RuntimeError)) else '')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
