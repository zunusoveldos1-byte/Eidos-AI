"""Worker-side synthesis to memory. No audio files or FFmpeg."""
import asyncio
from threading import Event
from .pcm import PCMAudio


class EdgeTTS:
    TIMEOUT = 45
    MAX_ENCODED_BYTES = 16 * 1024 * 1024

    def synthesize(self, text: str, voice: str, cancel: Event, *,
                   rate: int = 0, volume: int = 100) -> PCMAudio | None:
        if cancel.is_set():
            return None
        from eidos.agent.memory import require_public_text
        require_public_text(text)
        data = asyncio.run(self._collect(text, voice, cancel, rate, volume))
        if not data or cancel.is_set():
            return None
        audio = self._decode(data)
        return None if cancel.is_set() else audio

    @staticmethod
    def _decode(data: bytes) -> PCMAudio:
        import miniaudio
        # Edge's wire protocol is compressed. Native miniaudio decodes bytes,
        # without FFmpeg, a pathname or a temporary container file.
        decoded = miniaudio.decode(data, output_format=miniaudio.SampleFormat.SIGNED16,
                                   nchannels=1, sample_rate=16000)
        return PCMAudio(decoded.samples.tobytes())

    async def _collect(self, text, voice, cancel, rate=0, volume=100):
        import edge_tts
        rate = max(-50, min(100, int(rate)))
        volume = max(0, min(100, int(volume)))
        async def collect():
            data = bytearray()
            async for chunk in edge_tts.Communicate(text, voice, rate=f'{rate:+d}%',
                                                   volume=f'{volume - 100:+d}%').stream():
                if cancel.is_set():
                    return None
                if chunk['type'] == 'audio':
                    if len(data) + len(chunk['data']) > self.MAX_ENCODED_BYTES:
                        raise ValueError('Ответ озвучки превышает допустимый размер.')
                    data.extend(chunk['data'])
            return bytes(data)
        task = asyncio.create_task(collect())
        try:
            async with asyncio.timeout(self.TIMEOUT):
                while not task.done():
                    if cancel.is_set():
                        return None
                    await asyncio.wait({task}, timeout=.05)
                return await task
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


class SapiTTS:
    """SAPI COM objects are created, used and released in the caller's worker."""
    TIMEOUT = 45

    def list_voices(self) -> list[tuple[str, str]]:
        import comtypes
        from comtypes.client import CreateObject
        comtypes.CoInitialize()
        try:
            speaker = CreateObject('SAPI.SpVoice', dynamic=True)
            voices = speaker.GetVoices()
            return [(voices.Item(i).Id, voices.Item(i).GetDescription())
                    for i in range(voices.Count)]
        finally:
            speaker = voices = None
            comtypes.CoUninitialize()

    def synthesize(self, text: str, voice: str, cancel: Event, *,
                   rate: int = 0, volume: int = 100) -> PCMAudio | None:
        import time
        if cancel.is_set():
            return None
        try:
            import comtypes
            from comtypes.client import CreateObject
        except ImportError as exc:
            raise RuntimeError('Для локальной речи Windows установите comtypes.') from exc
        speaker = stream = voices = None
        initialized = False
        complete = False
        try:
            comtypes.CoInitialize()
            initialized = True
            speaker = CreateObject('SAPI.SpVoice', dynamic=True)
            voices = speaker.GetVoices()
            if not voices.Count:
                raise RuntimeError('В Windows не установлены голоса SAPI.')
            if voice:
                selected = next((voices.Item(i) for i in range(voices.Count)
                                 if voice in (voices.Item(i).Id, voices.Item(i).GetDescription())), None)
                if selected is None:
                    raise RuntimeError('Выбранный голос SAPI не установлен в Windows.')
                speaker.Voice = selected
            else:
                # Require an installed Russian voice for the default Russian UI.
                selected = next((voices.Item(i) for i in range(voices.Count)
                                 if '419' in voices.Item(i).GetAttribute('Language').lower().split(';')), None)
                if selected is None:
                    raise RuntimeError('Установите русский голос Windows и выберите его в настройках.')
                speaker.Voice = selected
            speaker.Rate = max(-10, min(10, round(int(rate) / 10)))
            speaker.Volume = max(0, min(100, int(volume)))
            stream = CreateObject('SAPI.SpMemoryStream', dynamic=True)
            stream.Format.Type = 18  # SAFT16kHz16BitMono
            speaker.AudioOutputStream = stream
            speaker.Speak(text, 1)  # SVSFlagsAsync: cancellation remains responsive.
            deadline = time.monotonic() + self.TIMEOUT
            while not speaker.WaitUntilDone(50):
                if cancel.is_set():
                    speaker.Speak('', 3)  # async + purge before release
                    return None
                if time.monotonic() >= deadline:
                    speaker.Speak('', 3)
                    raise TimeoutError('Превышено время синтеза SAPI.')
            complete = not cancel.is_set()
            audio = PCMAudio(bytes(stream.GetData())) if complete else None
        finally:
            speaker = stream = voices = None
            if initialized:
                comtypes.CoUninitialize()
        return audio if complete else None
