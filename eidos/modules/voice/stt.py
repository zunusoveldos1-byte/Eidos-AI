"""Lazy local Faster-Whisper engine, CPU by default."""

from pathlib import Path
from threading import Event
from typing import Callable, TYPE_CHECKING, Any
import json
import time
import sys
from eidos.core.metrics import METRICS

from eidos.core.config import AppConfig

if TYPE_CHECKING:
    import numpy as np


def _windows_short_path(path):
    import ctypes
    function = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
    function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    function.restype = ctypes.c_uint32
    size = function(str(path), None, 0)
    if not size:
        return ''
    buffer = ctypes.create_unicode_buffer(size)
    if not function(str(path), buffer, size):
        return ''
    return buffer.value


def native_model_path(path, *, platform=None):
    value = str(path.resolve())
    if (platform or sys.platform) != 'win32' or value.isascii():
        return value
    # Vosk 0.3.45's Windows native file reader does not reliably accept UTF-8
    # paths. A short ASCII alias addresses the same files without copying.
    short = _windows_short_path(path.resolve())
    if short and short.isascii():
        return short
    raise ValueError('Vosk для Windows требует ASCII-путь к модели; короткое имя NTFS недоступно. Выберите каталог без кириллицы.')


class WhisperSTT:
    def __init__(self) -> None:
        self._model: Any = None
        self._key: tuple[str, str] | None = None

    def transcribe(self, audio: 'np.ndarray', config: AppConfig, cache: Path,
                   progress: Callable[[str, str], None], cancel: Event) -> str:
        import numpy as np

        if audio.size < 2400:
            from .intents import RETRY_SPEECH
            raise ValueError('Запись пуста или слишком короткая. ' + RETRY_SPEECH)
        if not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < 0.0001:
            from .intents import RETRY_SPEECH
            raise ValueError('Запись содержит тишину. ' + RETRY_SPEECH)
        if cancel.is_set():
            return ''
        key = (config.whisper_model, config.device)
        if self._key != key:
            progress('loading', 'Подготовка модели Whisper…')
            import ctranslate2
            from faster_whisper import WhisperModel
            from faster_whisper.utils import download_model
            from huggingface_hub.errors import LocalEntryNotFoundError

            supported = ctranslate2.get_supported_compute_types(config.device)
            preferred = 'int8' if config.device == 'cpu' else 'float16'
            compute = preferred if preferred in supported else 'float32'
            if compute not in supported:
                raise RuntimeError('Устройство не поддерживает требуемый тип вычислений.')
            if compute != preferred:
                progress('loading', f'{preferred} недоступен: используется {compute}.')
            cache.mkdir(parents=True, exist_ok=True)
            try:
                model_path = download_model(config.whisper_model, cache_dir=str(cache), local_files_only=True)
                progress('loading', 'Загрузка Whisper из локального кеша…')
            except LocalEntryNotFoundError:
                from huggingface_hub.constants import HF_HUB_CACHE
                shared = Path(HF_HUB_CACHE)
                snapshots = shared / ('models--Systran--faster-whisper-' + config.whisper_model) / 'snapshots'
                if shared != cache and any(snapshots.glob('*/model.bin')):
                    model_path = download_model(config.whisper_model, cache_dir=str(shared), local_files_only=True)
                    progress('loading', 'Загрузка Whisper из локального кеша…')
                else:
                    raise ValueError('Модель Whisper не найдена в локальном кеше. Подготовьте её явно перед запуском голоса.') from None
            if cancel.is_set():
                return ''
            # Release an old CUDA model before allocating the replacement.
            self._model = None
            self._key = None
            started = time.perf_counter()
            self._model = WhisperModel(model_path, device=config.device, compute_type=compute,
                                       local_files_only=True)
            self._key = key
            METRICS.observe('model_load', (time.perf_counter() - started) * 1000, cold=True)
        if cancel.is_set():
            return ''
        progress('transcribing', 'Распознавание русской речи локально…')
        segments, _ = self._model.transcribe(audio, language='ru', beam_size=5,
                                             vad_filter=True, condition_on_previous_text=False,
                                             initial_prompt='Эйдос. Голосовой помощник Эйдос. YouTube. Блокнот. Переведи область экрана. Прочитай оригинал. Прочитай перевод.')
        parts = []
        uncertain = False
        deadline = time.monotonic() + 90
        for segment in segments:
            if cancel.is_set():
                return ''
            if time.monotonic() > deadline:
                raise ValueError('Распознавание превысило время ожидания. Выберите меньшую модель.')
            no_speech = getattr(segment, 'no_speech_prob', None)
            logprob = getattr(segment, 'avg_logprob', None)
            compression = getattr(segment, 'compression_ratio', None)
            if ((no_speech is not None and no_speech > .6) or
                    (logprob is not None and logprob < -1.) or
                    (compression is not None and compression > 2.4)):
                uncertain = True
            parts.append(segment.text.strip())
        if uncertain or not any(parts):
            from .intents import RETRY_SPEECH
            raise ValueError(RETRY_SPEECH)
        return ' '.join(parts).strip()


class VoskSTT:
    """Local PCM16 streaming recognizer; the model is loaded on the voice worker."""
    def __init__(self):
        self._model = self._key = self._recognizer = None
        self._parts = []

    def begin_stream(self, config, cache, progress, cancel):
        if cancel.is_set():
            return False
        path = Path(config.vosk_model_path)
        if not (path / 'am' / 'final.mdl').is_file() or not (path / 'conf' / 'model.conf').is_file():
            raise ValueError('Выберите распакованную локальную модель Vosk с am/final.mdl и conf/model.conf.')
        try:
            from vosk import Model, KaldiRecognizer
        except ImportError:
            raise ValueError('Vosk не установлен. Выполните python -m pip install ".[vosk]".') from None
        key = str(path.resolve())
        if self._key != key:
            progress('loading', 'Загрузка локальной модели Vosk…')
            self._model = self._key = None
            with METRICS.measure('model_load', cold=True):
                self._model = Model(native_model_path(path))
            self._key = key
        if cancel.is_set():
            return False
        self._recognizer = KaldiRecognizer(self._model, 16000)
        self._parts = []
        self._deadline = None
        self._stream_timeout = config.voice_max_seconds + 90
        return True

    def feed(self, samples, cancel):
        import numpy as np
        if cancel.is_set():
            return
        if self._deadline is None:
            self._deadline = time.monotonic() + self._stream_timeout
        if time.monotonic() > self._deadline:
            raise ValueError('Распознавание Vosk превысило время ожидания.')
        if isinstance(samples, bytes):
            if len(samples) % 2:
                raise ValueError('Некорректные аудиоданные PCM16.')
            pcm = samples
        else:
            # Compatibility with Whisper/wake arrays; raw capture bypasses this.
            if not np.isfinite(samples).all():
                raise ValueError('Некорректные аудиоданные.')
            pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
        with METRICS.measure('stt_chunk'):
            if self._recognizer.AcceptWaveform(pcm):
                self._parts.append(json.loads(self._recognizer.Result()).get('text', '').strip())

    def finish_stream(self, cancel):
        try:
            if cancel.is_set():
                return ''
            self._parts.append(json.loads(self._recognizer.FinalResult()).get('text', '').strip())
            text = ' '.join(part for part in self._parts if part)
            if not text:
                from .intents import RETRY_SPEECH
                raise ValueError(RETRY_SPEECH)
            return text
        finally:
            self._recognizer = None
            self._parts = []

    def transcribe(self, audio, config, cache, progress, cancel):
        if not self.begin_stream(config, cache, progress, cancel):
            return ''
        progress('transcribing', 'Распознавание русской речи локально…')
        try:
            size, step = (len(audio), 8000) if isinstance(audio, bytes) else (audio.size, 4000)
            for offset in range(0, size, step):
                self.feed(audio[offset:offset + step], cancel)
            return self.finish_stream(cancel)
        finally:
            self._recognizer = None


class LocalSTT:
    """Keep exactly one model engine alive, preserving the transcribe interface."""
    def __init__(self):
        self._engine = None
        self._name = None

    def select(self, config):
        if self._name != config.stt_engine:
            self._engine = None
            self._name = config.stt_engine
            self._engine = VoskSTT() if self._name == 'vosk' else WhisperSTT()
        return self._engine

    def transcribe(self, audio, config, cache, progress, cancel):
        return self.select(config).transcribe(audio, config, cache, progress, cancel)
