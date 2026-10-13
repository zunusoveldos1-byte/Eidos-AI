"""Lazy local Faster-Whisper engine, CPU by default."""

from pathlib import Path
from threading import Event
from typing import Callable, TYPE_CHECKING, Any

from eidos.core.config import AppConfig

if TYPE_CHECKING:
    import numpy as np


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
                progress('loading', 'Первая загрузка модели Whisper: требуется интернет…')
                model_path = download_model(config.whisper_model, cache_dir=str(cache))
            if cancel.is_set():
                return ''
            self._model = WhisperModel(model_path, device=config.device, compute_type=compute,
                                       local_files_only=True)
            self._key = key
        if cancel.is_set():
            return ''
        progress('transcribing', 'Распознавание русской речи локально…')
        segments, _ = self._model.transcribe(audio, language='ru', beam_size=5,
                                             vad_filter=True, condition_on_previous_text=False,
                                             initial_prompt='Эйдос. Голосовой помощник Эйдос. YouTube. Блокнот. Переведи область экрана. Прочитай оригинал. Прочитай перевод.')
        parts = []
        uncertain = False
        for segment in segments:
            if cancel.is_set():
                return ''
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
