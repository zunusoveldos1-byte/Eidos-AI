"""Opt-in local audio input. Never opens a microphone on import.

Input is owned by one QThread; audio callbacks only copy into a bounded queue.
No model downloads, Qt widgets, HTTP calls or STT inside the audio callback.
"""
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time
from uuid import uuid4

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

RATE = 16000
FRAME = 512


@dataclass(frozen=True)
class InputOptions:
    pre_roll_seconds: float = .75
    silence_seconds: float = .64
    onset_seconds: float = 5.
    max_seconds: float = 30.
    vad_threshold: float = .55
    wake_threshold: float = .6
    microphone_name: str | None = None
    allow_default_fallback: bool = True
    # Two independently trained ONNX keyword heads, NOT names of built-in models.
    wake_models: tuple[str, ...] = ()
    mel_model: str | None = None
    embedding_model: str | None = None

    def __post_init__(self):
        if not (0 <= self.pre_roll_seconds <= 1 and
                .032 <= self.silence_seconds <= 3 and
                .032 <= self.onset_seconds <= 30 and
                .032 <= self.max_seconds <= 120 and
                0 < self.vad_threshold < 1 and 0 < self.wake_threshold < 1):
            raise ValueError('Некорректные параметры аудиовхода')


class LinearResampler:
    """Stateful fallback resampler; preserves positions across callback boundaries.

    Linear interpolation is a baseline, not a band-limited production resampler.
    Prefer a native 16 kHz input; evaluate a soxr adapter for noisy 44.1/48 kHz.
    """
    def __init__(self, rate):
        self.step = rate / RATE
        self.tail = np.empty(0, dtype=np.float32)
        self.position = 0.

    def feed(self, samples):
        data = np.concatenate((self.tail, samples))
        if len(data) < 2:
            self.tail = data
            return np.empty(0, dtype=np.float32)
        count = max(0, int(np.ceil((len(data) - 1 - self.position) / self.step)))
        positions = self.position + np.arange(count) * self.step
        result = np.interp(positions, np.arange(len(data)), data).astype(np.float32)
        self.position += count * self.step - (len(data) - 1)
        self.tail = data[-1:]
        return result


class CaptureGate:
    """Pure frame-based recording state, independent of devices and Qt."""
    def __init__(self, options):
        self.options = options
        self.ring = deque(maxlen=int(options.pre_roll_seconds * RATE / FRAME))
        self.source = None
        self.chunks = []
        self.held = False
        self.samples = self.elapsed = self.silence = 0
        self.heard = False

    def reset(self):
        self.ring.clear()
        self.source = None
        self.chunks = []
        self.samples = self.elapsed = self.silence = 0
        self.heard = False

    def release(self):
        result = None
        if self.source is not None and self.heard:
            result = (np.concatenate(self.chunks), self.source)
        self.reset()
        return result

    def feed(self, audio, probability, wake, held):
        rising = held and not self.held
        falling = not held and self.held
        self.held = held
        if falling and self.source == 'ptt':
            return self.release()
        if self.source is None:
            if rising or (wake and not held):
                self.source = 'ptt' if rising else wake
                self.chunks = list(self.ring)
                self.samples = sum(len(x) for x in self.chunks)
                # Pre-roll contains the keyword: it must not count as command speech.
                self.heard = False
            else:
                self.ring.append(audio.copy())
                return None
        limit = round(self.options.max_seconds * RATE)
        take = max(0, min(len(audio), limit - self.elapsed))
        self.chunks.append(audio[:take].copy())
        self.samples += take
        self.elapsed += len(audio)
        speaking = probability >= self.options.vad_threshold
        self.heard |= speaking
        self.silence = 0 if speaking else self.silence + len(audio)
        if self.elapsed >= limit:
            return self.release()
        if self.source != 'ptt':
            if self.heard and self.silence >= self.options.silence_seconds * RATE:
                return self.release()
            if not self.heard and self.elapsed >= self.options.onset_seconds * RATE:
                self.reset()
        return None


class SileroProbability:
    """Stateful CPU Silero adapter for the model bundled with Faster-Whisper.

    Supports the installed encoder h/c schema and the standard state/sr schema.
    Model state belongs to this instance; the underlying session is read-only.
    """
    def __init__(self):
        from faster_whisper.vad import get_vad_model
        self.session = get_vad_model().session
        self.names = {x.name for x in self.session.get_inputs()}
        if self.names not in ({'input', 'h', 'c'}, {'input', 'state', 'sr'}):
            raise RuntimeError('Неизвестный формат Silero: проверьте версию faster-whisper')
        self.reset()

    def reset(self):
        self.context = np.zeros((1, 64), np.float32)
        self.h = np.zeros((1, 1, 128), np.float32)
        self.c = np.zeros_like(self.h)
        self.state = np.zeros((2, 1, 128), np.float32)

    def __call__(self, audio):
        if audio.shape != (FRAME,):
            raise ValueError('Silero ожидает 512 отсчётов, 16 кГц')
        data = np.concatenate((self.context, audio[None, :]), axis=1)
        if 'h' in self.names:
            out, self.h, self.c = self.session.run(None, {'input': data, 'h': self.h, 'c': self.c})
        else:
            out, self.state = self.session.run(None, {
                'input': data, 'state': self.state, 'sr': np.array(RATE, dtype=np.int64)})
        self.context = data[:, -64:].copy()
        return float(np.asarray(out).reshape(-1)[0])


class WakeModels:
    def __init__(self, options):
        from openwakeword.model import Model
        for path in options.wake_models:
            if not Path(path).is_file():
                raise FileNotFoundError('Нет wake-модели: ' + path)
        kwargs = {}
        if options.mel_model:
            kwargs['melspec_model_path'] = options.mel_model
        if options.embedding_model:
            kwargs['embedding_model_path'] = options.embedding_model
        self.model = Model(wakeword_models=list(options.wake_models),
                           inference_framework='onnx', **kwargs)
        self.threshold = options.wake_threshold
        self.pending = np.empty(0, np.int16)

    def reset(self):
        self.pending = np.empty(0, np.int16)
        self.model.reset()

    def __call__(self, audio):
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
        self.pending = np.concatenate((self.pending, pcm))
        detected = None
        while len(self.pending) >= 1280:  # openWakeWord: 80 ms at 16 kHz
            scores = self.model.predict(self.pending[:1280])
            self.pending = self.pending[1280:]
            if scores:
                name = max(scores, key=scores.get)
                if scores[name] >= self.threshold:
                    detected = name
        return detected


class LocalAudioInput(QThread):
    audio_ready = pyqtSignal(object, str, str)  # float32/16 kHz, id, source
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, options=None, parent=None):
        super().__init__(parent)
        self.options = options or InputOptions()
        self.stop_event = Event()
        self.ptt = Event()
        self.lock = Lock()
        self.enabled = True
        self.blocked = False
        self.generation = 0
        self.submitted = None

    def set_ptt(self, held):
        self.ptt.set() if held else self.ptt.clear()

    def set_enabled(self, enabled):
        with self.lock:
            self.enabled = bool(enabled)
            self.generation += 1
        if not enabled:
            self.ptt.clear()

    def set_blocked(self, blocked):
        """Call for the entire STT/agent/TTS operation, including playback tail."""
        with self.lock:
            if self.blocked != bool(blocked):
                self.blocked = bool(blocked)
                self.generation += 1

    def shutdown(self):
        self.stop_event.set()  # GUI must wait for finished asynchronously, never wait().

    def _permission(self):
        with self.lock:
            return self.enabled and not self.blocked, self.generation

    def is_current(self, recording_id):
        with self.lock:
            return (not self.stop_event.is_set() and self.enabled and
                    self.submitted == (recording_id, self.generation))

    def _device(self, sd):
        name = self.options.microphone_name
        if name:
            matches = [(i, d) for i, d in enumerate(sd.query_devices())
                       if d['max_input_channels'] and d['name'] == name]
            if matches:
                return matches[0][0], matches[0][1]
            if not self.options.allow_default_fallback:
                raise OSError('Выбранный микрофон отключён')
            self.status.emit('Выбранный микрофон недоступен; используется системный')
        return None, sd.query_devices(kind='input')

    def run(self):
        try:
            import sounddevice as sd
            vad = SileroProbability()
        except Exception as exc:
            self.error.emit('Аудиовход не запущен: ' + str(exc))
            return
        wake = None
        if self.options.wake_models:
            try:
                wake = WakeModels(self.options)
            except Exception as exc:
                self.error.emit('Wake Word недоступен; PTT остаётся доступен: ' + str(exc))
        gate = CaptureGate(self.options)
        backoff = .5
        while not self.stop_event.is_set():
            try:
                self._capture(sd, vad, wake, gate)
                backoff = .5
            except Exception as exc:
                gate.reset()
                vad.reset()
                if wake:
                    wake.reset()
                if not self.stop_event.is_set():
                    self.error.emit('Микрофон/поток: ' + str(exc) + '; повторное подключение')
                    self.stop_event.wait(backoff)
                    backoff = min(10., backoff * 2)
        self.status.emit('Аудиовход остановлен')

    def _capture(self, sd, vad, wake, gate):
        queue = Queue(maxsize=8)
        damaged = Event()
        device, info = self._device(sd)
        native_rate = RATE
        sd.check_input_settings(device=device, channels=1, dtype='int16', samplerate=RATE)
        resampler = None
        pending = np.empty(0, np.float32)
        gate.reset()
        gate.held = self.ptt.is_set()  # reconnect must not turn an old held key into a new press
        vad.reset()
        if wake:
            wake.reset()
        _, generation = self._permission()

        def callback(indata, frames, timing, status):
            if status:
                damaged.set()
                return
            allowed, epoch = self._permission()
            if not allowed or self.stop_event.is_set():
                return
            try:
                queue.put_nowait((bytes(indata), epoch, self.ptt.is_set()))
            except Full:
                damaged.set()  # a discontinuous command is discarded, never executed

        stream = sd.RawInputStream(device=device, channels=1, dtype='int16',
                                samplerate=native_rate, blocksize=round(native_rate * .032),
                                callback=callback)
        try:
            stream.start()
            self.status.emit('Микрофон готов · Ctrl+Space' + (' · Wake Word' if wake else ' · только PTT'))
            last_frame = time.monotonic()
            while not self.stop_event.is_set():
                allowed, epoch = self._permission()
                if epoch != generation:
                    gate.reset()
                    gate.held = self.ptt.is_set()
                    vad.reset()
                    if wake:
                        wake.reset()
                    pending = np.empty(0, np.float32)
                    resampler = LinearResampler(native_rate) if native_rate != RATE else None
                    generation = epoch
                    last_frame = time.monotonic()
                if damaged.is_set():
                    raise OSError('Потеря аудиоданных; незавершённая команда отброшена')
                if not stream.active:
                    raise OSError('Устройство остановило поток')
                try:
                    audio, audio_epoch, held = queue.get(timeout=.05)
                except Empty:
                    if allowed and gate.source == 'ptt' and not self.ptt.is_set():
                        self._submit(gate.release())
                        gate.held = False
                    if allowed and time.monotonic() - last_frame > 2:
                        raise OSError('Микрофон перестал передавать данные')
                    continue
                last_frame = time.monotonic()
                if not allowed or audio_epoch != generation:
                    continue
                audio = np.frombuffer(audio, dtype='<i2').astype(np.float32) / 32768.
                pending = np.concatenate((pending, audio))
                while len(pending) >= FRAME:
                    block, pending = pending[:FRAME], pending[FRAME:]
                    probability = vad(block)
                    detected = wake(block) if wake and gate.source is None and not held else None
                    result = gate.feed(block, probability, detected, held)
                    if result:
                        self._submit(result)
                        # Block in the worker BEFORE emitting another command to Qt.
                        pending = np.empty(0, np.float32)
                        break
        finally:
            try:
                stream.abort()
            finally:
                stream.close()

    def _submit(self, result):
        if result is None:
            return
        with self.lock:
            if not self.enabled or self.blocked or self.stop_event.is_set():
                return
            self.blocked = True
            self.generation += 1
            recording_id = uuid4().hex
            self.submitted = (recording_id, self.generation)
        self.audio_ready.emit(result[0], recording_id, result[1])


class WindowsPushToTalk:
    """Global Ctrl+Space without keyboard hooks or extra packages."""
    def __init__(self, on_change):
        self.on_change = on_change
        self.stop_event = Event()
        self.thread = None

    def start(self):
        import sys
        if sys.platform != 'win32':
            raise OSError('Глобальный PTT реализован для Windows')
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = Thread(target=self._run, name='EidosPTT', daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.on_change(False)

    def _run(self):
        import ctypes
        key_state = ctypes.windll.user32.GetAsyncKeyState
        previous = False
        try:
            while not self.stop_event.wait(.015):
                held = bool(key_state(0x11) & 0x8000 and key_state(0x20) & 0x8000)
                if held != previous:
                    previous = held
                    self.on_change(held)
        finally:
            self.on_change(False)
