from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int


class ScreenTranslator(Protocol):
    def recognize(self, region: ScreenRegion) -> str: ...
    def translate(self, text: str, target_language: str = 'ru') -> str: ...


class DisconnectedOCR:
    status = 'Модуль пока не подключён'

    def recognize(self, region: ScreenRegion) -> str:
        raise NotImplementedError(self.status)

    def translate(self, text: str, target_language: str = 'ru') -> str:
        raise NotImplementedError(self.status)


class JonSnowTranslator:
    """Adapter over the existing local OCR and text-only translation engines."""
    def __init__(self, ocr=None, translator=None):
        if ocr is None:
            from .multilingual import ScreenOCR
            ocr = ScreenOCR()
        if translator is None:
            from .engine import OnlineTranslator
            translator = OnlineTranslator()
        self.ocr, self.translator = ocr, translator

    def process(self, image, source, target, provider, cancel, progress=None, recognized=None):
        if provider != 'google':
            raise ValueError('Выберите провайдер перевода. Google получает только распознанный текст.')
        if cancel.is_set():
            return []
        if hasattr(self.ocr, 'progress'):
            self.ocr.progress = progress
        lines = self.ocr.recognize(image, source)
        if cancel.is_set():
            return []
        if not lines:
            raise RuntimeError('Текст не найден. Выделите более крупные надписи.')
        if recognized:
            recognized('\n'.join(line.text for line in lines))
        cache = {}
        for index, line in enumerate(lines, 1):
            if cancel.is_set():
                return []
            if progress:
                progress(f'Перевод: {index} из {len(lines)} строк')
            if line.text not in cache:
                from .engine import OnlineTranslator
                if isinstance(self.translator, OnlineTranslator):
                    cache[line.text] = self.translator.translate(line.text, source, target, cancel=cancel)
                else:
                    cache[line.text] = self.translator.translate(line.text, source, target)
            line.translation = cache[line.text]
        return [] if cancel.is_set() else lines
