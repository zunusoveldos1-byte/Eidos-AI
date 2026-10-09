"""Bounded in-memory microphone recording in a worker thread."""

from dataclasses import dataclass
from threading import Event
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class Microphone:
    index: int
    name: str


def list_microphones() -> list[Microphone]:
    import sounddevice as sd

    hosts = sd.query_hostapis()
    return [Microphone(index, f"{device['name']} · {hosts[device['hostapi']]['name']}")
            for index, device in enumerate(sd.query_devices()) if device['max_input_channels'] > 0]


def resample(samples: 'np.ndarray', sample_rate: int) -> 'np.ndarray':
    """Linear resampling to Whisper's 16 kHz mono input."""
    import numpy as np

    if sample_rate == 16000 or samples.size == 0:
        return samples.astype(np.float32, copy=False)
    count = round(samples.size * 16000 / sample_rate)
    positions = np.arange(count, dtype=np.float64) * sample_rate / 16000
    return np.interp(positions, np.arange(samples.size), samples).astype(np.float32)


class Recorder:
    MAX_SECONDS = 120

    def record(self, device: int | None, stop: Event, cancel: Event,
               started: Callable[[], None]) -> 'np.ndarray | None':
        import numpy as np
        import sounddevice as sd

        if cancel.is_set():
            return None
        info = sd.query_devices(device, 'input')
        sample_rate = int(info['default_samplerate'])
        sd.check_input_settings(device=device, channels=1, dtype='float32', samplerate=sample_rate)
        chunks: list[np.ndarray] = []
        count = 0
        overflow = False
        limit = sample_rate * self.MAX_SECONDS

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            nonlocal count, overflow
            if status:
                overflow = True
            if stop.is_set() or cancel.is_set():
                return
            remaining = limit - count
            if remaining > 0:
                chunk = indata[:remaining, 0].copy()
                chunks.append(chunk)
                count += chunk.size
            if count >= limit:
                stop.set()

        stream = sd.InputStream(device=device, channels=1, samplerate=sample_rate,
                                dtype='float32', callback=callback)
        try:
            if cancel.is_set():
                return None
            stream.start()
            started()
            while not stop.wait(0.05) and not cancel.is_set():
                if not stream.active:
                    raise OSError('Микрофон отключён во время записи')
        finally:
            try:
                stream.abort()
            finally:
                stream.close()
        if cancel.is_set():
            return None
        if overflow:
            raise OSError('Потеря аудиоданных. Закройте другие аудиоприложения и повторите запись.')
        audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)
        return resample(audio, sample_rate)
