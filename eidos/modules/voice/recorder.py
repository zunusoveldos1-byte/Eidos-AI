"""Bounded in-memory microphone recording in a worker thread."""

from dataclasses import dataclass
from threading import Event, Lock
from typing import Callable, TYPE_CHECKING
from time import perf_counter

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
    SILENCE_SECONDS = .65
    SPEECH_THRESHOLD = .012
    PRE_ROLL_SECONDS = .3

    def __init__(self) -> None:
        self.level_callback: Callable[[float], None] | None = None
        self.activity_callback: Callable[[float, bool], None] | None = None
        self.speech_callback: Callable[[], None] | None = None
        self.end_of_speech = False
        self.sensitivity = .5
        self.max_seconds = self.MAX_SECONDS
        self._configured = False
        self.chunk_callback = None
        self.speech_ended_at = None
        self._stream = None
        self._stream_key = None
        self._callback = None
        self._callback_lock = Lock()

    def _dispatch(self, *args):
        # Brief PCM/VAD work only; the recognizer never runs on this callback.
        with self._callback_lock:
            if self._callback is not None:
                self._callback(*args)

    def close(self):
        with self._callback_lock:
            self._callback = None
        stream, self._stream = self._stream, None
        self._stream_key = None
        if stream is not None:
            try:
                stream.abort()
            finally:
                stream.close()

    def configure(self, config) -> None:
        self.sensitivity = config.voice_sensitivity
        self.max_seconds = config.voice_max_seconds
        self.wait_for_speech = getattr(config, "continuous_listening", False)
        self.end_of_speech = True
        self.continuous = getattr(config, 'continuous_listening', False)
        self._configured = True

    def record(self, device: int | None, stop: Event, cancel: Event,
               started: Callable[[], None]) -> 'np.ndarray | None':
        import numpy as np
        import sounddevice as sd
        from collections import deque
        from .vad import SileroVAD
        from eidos.core.metrics import METRICS

        if cancel.is_set():
            return None
        # Initialize weights outside the callback and before opening the device.
        if getattr(self, 'vad', None) is None:
            self.vad = SileroVAD()
        self.vad.reset()
        sample_rate = 16000
        sd.check_input_settings(device=device, channels=1, dtype='int16', samplerate=sample_rate)
        self.speech_ended_at = None
        streaming = self.chunk_callback is not None
        pending = deque(maxlen=32)
        chunks, pre_roll = [], deque(maxlen=10)
        heard_speech = endpoint = False
        silence_count = elapsed_count = count = 0
        dropped = overflow = False
        auto_end = self.end_of_speech
        seconds = self.max_seconds if self._configured else self.SPEECH_MAX_SECONDS if auto_end else self.MAX_SECONDS
        limit = sample_rate * seconds
        threshold = .75 - .5 * self.sensitivity

        def callback(indata, frames, time_info, status):
            nonlocal dropped, overflow
            if status:
                overflow = True
            if cancel.is_set() or stop.is_set():
                return
            if len(pending) == pending.maxlen:
                dropped = True
                return
            # Copy PortAudio's ephemeral buffer. No VAD, STT, resampling or I/O here.
            pending.append((perf_counter(), bytes(indata)))

        def process(pcm, captured):
            nonlocal heard_speech, silence_count, elapsed_count, count, endpoint
            # RawInputStream normally returns exactly 512 samples; split larger
            # host blocks without changing the sample values.
            for offset in range(0, len(pcm), 1024):
                frame = pcm[offset:offset + 1024]
                if len(frame) != 1024:
                    raise OSError('Некорректный размер кадра микрофона PCM16.')
                voiced = self.vad(frame) >= threshold
                level = float(np.sqrt(np.mean((np.frombuffer(frame, dtype='<i2').astype(np.float32) / 32768.) ** 2)))
                if self.level_callback:
                    self.level_callback(level)
                if self.activity_callback:
                    self.activity_callback(level, voiced)
                elapsed_count += 512
                if voiced:
                    self.speech_ended_at = captured
                if auto_end and not heard_speech:
                    if voiced:
                        heard_speech = True
                        if self.speech_callback:
                            self.speech_callback()
                        for item in pre_roll:
                            if streaming:
                                self.chunk_callback(item)
                            else:
                                chunks.append(item)
                            count += len(item) // 2
                        pre_roll.clear()
                    else:
                        pre_roll.append(frame)
                        if not getattr(self, 'wait_for_speech', False) and elapsed_count >= sample_rate * self.ONSET_TIMEOUT:
                            stop.set()
                            endpoint = True
                            break
                        continue
                remaining = limit - count
                if remaining <= 0:
                    stop.set()
                    endpoint = True
                    break
                frame = frame[:remaining * 2]
                if streaming:
                    self.chunk_callback(frame)
                else:
                    chunks.append(frame)
                count += len(frame) // 2
                silence_count = silence_count + 512 if not voiced else 0
                if count >= limit or (auto_end and silence_count >= sample_rate * self.SILENCE_SECONDS):
                    stop.set()
                    endpoint = True
                    break

        key = (device, sample_rate)
        if self._stream is not None and (self._stream_key != key or not self._stream.active):
            self.close()
        new_stream = self._stream is None
        if new_stream:
            self._stream = sd.RawInputStream(device=device, channels=1, samplerate=sample_rate,
                                            blocksize=512, dtype='int16', callback=self._dispatch)
            self._stream_key = key
        stream = self._stream
        with self._callback_lock:
            self._callback = callback
        failed = True
        try:
            if cancel.is_set():
                return None
            if new_stream or not stream.active:
                stream.start()
            started()
            while not cancel.is_set():
                while pending and not cancel.is_set():
                    queued, pcm = pending.popleft()
                    METRICS.observe('audio_buffering', max(0., (perf_counter() - queued) * 1000))
                    process(pcm, queued)
                    if endpoint:
                        pending.clear()
                        break
                if stop.is_set():
                    break
                if not stream.active:
                    raise OSError('Микрофон отключён во время записи')
                cancel.wait(.005)
            failed = False
        finally:
            with self._callback_lock:
                self._callback = None
            if failed or cancel.is_set() or not getattr(self, 'continuous', False):
                self.close()
        if cancel.is_set():
            return None
        if overflow or dropped:
            self.close()
            raise OSError('Потеря аудиоданных. Закройте другие аудиоприложения и повторите запись.')
        if streaming:
            return np.empty(0, dtype=np.float32)
        # Only the optional Whisper engine needs a float array; Vosk gets raw bytes.
        return np.frombuffer(b''.join(chunks), dtype='<i2').astype(np.float32) / 32768.
