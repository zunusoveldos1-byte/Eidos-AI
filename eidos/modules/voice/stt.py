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
            raise ValueError('Запись пуста или слишком короткая. Запишите команду ещё раз.')
        if not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < 0.0001:
            raise ValueError('Запись содержит тишину. Проверьте выбранный микрофон.')
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
                                             vad_filter=True, condition_on_previous_text=False)
        parts = []
        for segment in segments:
            if cancel.is_set():
                return ''
            parts.append(segment.text.strip())
        return ' '.join(parts).strip()
