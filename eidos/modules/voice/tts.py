"""Online synthesis in worker-owned asyncio loop; only temporary MP3 files."""

import asyncio
import os
from pathlib import Path
from threading import Event
import tempfile


class EdgeTTS:
    TIMEOUT = 45

    def synthesize(self, text: str, voice: str, cancel: Event) -> Path | None:
        if cancel.is_set():
            return None
        fd, name = tempfile.mkstemp(prefix='eidos-', suffix='.mp3')
        os.close(fd)
        path = Path(name)
        try:
            completed = asyncio.run(self._save(text, voice, path, cancel))
            if not completed or cancel.is_set():
                path.unlink(missing_ok=True)
                return None
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    async def _save(self, text: str, voice: str, path: Path, cancel: Event) -> bool:
        import edge_tts

        task = asyncio.create_task(edge_tts.Communicate(text, voice).save(str(path)))
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
