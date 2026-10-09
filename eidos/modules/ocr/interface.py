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
