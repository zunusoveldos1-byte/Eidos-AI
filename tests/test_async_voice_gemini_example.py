import asyncio
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from examples.async_voice_gemini import ask_gemini, speak, play_pcm


def fake_types(monkeypatch):
    types = SimpleNamespace(GenerateContentConfig=lambda **kw: kw, ThinkingConfig=lambda **kw: kw)
    monkeypatch.setitem(sys.modules, 'google', SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'google.genai', SimpleNamespace(types=types))


def test_gemini_await_yields_and_limits_spoken_reply(monkeypatch):
    fake_types(monkeypatch)
    requests, ticks = [], []
    async def generate(**kwargs):
        requests.append(kwargs)
        await asyncio.sleep(.03)
        return SimpleNamespace(text='Привет. **Я готов.** Третье предложение.')
    async def check():
        task = asyncio.create_task(ask_gemini(SimpleNamespace(models=SimpleNamespace(generate_content=generate)), 'Привет'))
        while not task.done():
            ticks.append(True)
            await asyncio.sleep(.005)
        return await task
    assert asyncio.run(check()) == 'Привет. Я готов.'
    assert len(ticks) >= 2
    assert requests[0]['model'] == 'gemini-2.5-flash'
    assert requests[0]['config']['thinking_config']['thinking_budget'] == 0


def test_secret_never_reaches_gemini(monkeypatch):
    fake_types(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(ask_gemini(SimpleNamespace(), 'known-credential', secret_values=('known-credential',)))


def test_tts_cancellation_closes_network_stream_without_files(monkeypatch):
    events = []
    async def stream():
        try:
            events.append('started')
            await asyncio.sleep(100)
            yield {'type': 'audio', 'data': b'test'}
        finally:
            events.append('closed')
    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(Communicate=lambda *a, **k: SimpleNamespace(stream=stream)))
    async def cancel():
        task = asyncio.create_task(speak('Привет'))
        while not events:
            await asyncio.sleep(.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(cancel())
    assert events == ['started', 'closed']


def test_playback_cancellation_releases_native_device(monkeypatch):
    from eidos.modules.voice.pcm import PCMAudio
    devices = []
    class Device:
        def __init__(self, **kw): self.closed=False; devices.append(self)
        def start(self, generator): pass
        def close(self): self.closed=True
    monkeypatch.setitem(sys.modules, 'miniaudio', SimpleNamespace(
        PlaybackDevice=Device, SampleFormat=SimpleNamespace(SIGNED16=2)))
    async def cancel():
        task = asyncio.create_task(play_pcm(PCMAudio(bytes(1024))))
        while not devices: await asyncio.sleep(.005)
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
    asyncio.run(cancel())
    assert devices[0].closed
