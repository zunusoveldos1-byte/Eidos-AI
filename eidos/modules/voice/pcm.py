"""Audio payloads contain samples, never a filesystem path."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PCMAudio:
    data: bytes
    sample_rate: int = 16000
    channels: int = 1

    def __post_init__(self):
        if not isinstance(self.data, bytes) or len(self.data) % (2 * self.channels):
            raise ValueError('Ожидается PCM16 с целым числом кадров.')
        if self.sample_rate <= 0 or self.channels not in (1, 2):
            raise ValueError('Некорректный формат PCM.')

