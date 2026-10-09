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
    SPEECH_MAX_SECONDS = 30
    ONSET_TIMEOUT = 5
    SILENCE_SECONDS = .8
    SPEECH_THRESHOLD = .012
    PRE_ROLL_SECONDS = .3

    def __init__(self) -> None:
        self.level_callback: Callable[[float], None] | None = None
        self.end_of_speech = False

    def record(self, device: int | None, stop: Event, cancel: Event,
               started: Callable[[], None]) -> 'np.ndarray | None':
        import numpy as np
        import sounddevice as sd

        if cancel.is_set():
            return None
        info = sd.query_devices(device, 'input')
        sample_rate = int(info['default_samplerate'])
        sd.check_input_settings(device=device, channels=1, dtype='float32', samplerate=sample_rate)
        from collections import deque
        chunks: list[np.ndarray] = []
        pre_roll = deque()
        pre_count = 0
        heard_speech = False
        silence_count = 0
        elapsed_count = 0
        level_count = 0
        count = 0
        overflow = False
        auto_end = self.end_of_speech
        limit = sample_rate * (self.SPEECH_MAX_SECONDS if auto_end else self.MAX_SECONDS)

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            nonlocal count, overflow, pre_count, heard_speech, silence_count, elapsed_count, level_count
            if status:
                overflow = True
            if stop.is_set() or cancel.is_set():
                return
            rms = float(np.sqrt(np.mean(np.square(indata[:, 0], dtype=np.float64))))
            level_count += frames
            if self.level_callback and level_count >= sample_rate / 10:
                level_count = 0
                self.level_callback(max(0., min(1., rms)))
            elapsed_count += frames
            if auto_end:
                if not heard_speech:
                    if rms >= self.SPEECH_THRESHOLD:
                        heard_speech = True
                        chunks.extend(pre_roll)
                        count = pre_count
                        pre_roll.clear()
                    else:
                        pre_roll.append(indata[:, 0].copy())
                        pre_count += frames
                        while pre_roll and pre_count > sample_rate * self.PRE_ROLL_SECONDS:
                            pre_count -= pre_roll.popleft().size
                        if elapsed_count >= sample_rate * self.ONSET_TIMEOUT:
                            stop.set()
                        return
                silence_count = silence_count + frames if rms < self.SPEECH_THRESHOLD else 0
            remaining = limit - count
            if remaining > 0:
                chunk = indata[:remaining, 0].copy()
                chunks.append(chunk)
                count += chunk.size
            if count >= limit or (auto_end and silence_count >= sample_rate * self.SILENCE_SECONDS):
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
