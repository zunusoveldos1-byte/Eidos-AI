"""Online synthesis in worker-owned asyncio loop; only temporary MP3 files."""

import asyncio
import os
from pathlib import Path
from threading import Event
import tempfile


class EdgeTTS:
    TIMEOUT = 45

    def synthesize(self, text: str, voice: str, cancel: Event, *,
                   rate: int = 0, volume: int = 100) -> Path | None:
        if cancel.is_set():
            return None
        fd, name = tempfile.mkstemp(prefix='eidos-', suffix='.mp3')
        os.close(fd)
        path = Path(name)
        try:
            operation = (self._save(text, voice, path, cancel) if rate == 0 and volume == 100
                         else self._save(text, voice, path, cancel, rate, volume))
            completed = asyncio.run(operation)
            if not completed or cancel.is_set():
                path.unlink(missing_ok=True)
                return None
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    async def _save(self, text: str, voice: str, path: Path, cancel: Event,
                    rate: int = 0, volume: int = 100) -> bool:
        import edge_tts

        rate = max(-50, min(100, int(rate)))
        volume = max(0, min(100, int(volume)))
        task = asyncio.create_task(edge_tts.Communicate(
            text, voice, rate=f'{rate:+d}%', volume=f'{volume - 100:+d}%').save(str(path)))
        try:
            async with asyncio.timeout(self.TIMEOUT):
                while not task.done():
                    if cancel.is_set():
                        return False
                    await asyncio.wait({task}, timeout=0.1)
                await task
                return True
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
                   rate: int = 0, volume: int = 100) -> Path | None:
        import time
        if cancel.is_set():
            return None
        try:
            import comtypes
            from comtypes.client import CreateObject
        except ImportError as exc:
            raise RuntimeError('Для локальной речи Windows установите comtypes.') from exc
        fd, name = tempfile.mkstemp(prefix='eidos-', suffix='.wav')
        os.close(fd)
        path = Path(name)
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
            stream = CreateObject('SAPI.SpFileStream', dynamic=True)
            stream.Open(str(path), 3, False)  # SSFMCreateForWrite
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
        finally:
            try:
                if stream is not None:
                    stream.Close()
            finally:
                speaker = stream = voices = None
                if initialized:
                    comtypes.CoUninitialize()
                if not complete:
                    path.unlink(missing_ok=True)
        return path if complete else None
