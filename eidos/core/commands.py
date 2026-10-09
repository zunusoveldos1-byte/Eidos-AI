"""Russian button-activated command handling."""

from datetime import datetime
import re
from typing import Callable, Protocol


class AssistantProvider(Protocol):
    """Future Ollama/OpenAI adapter; called only by a background worker."""

    def respond(self, text: str) -> str: ...


class DisconnectedProvider:
    def respond(self, text: str) -> str:
        return 'Не удалось определить команду. Скажите «Помощь». AI-модель для свободного общения пока не подключена.'


class CommandHandler:
    MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
              'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря')

    def __init__(self, now: Callable[[], datetime] = datetime.now,
                 provider: AssistantProvider | None = None) -> None:
        self.now = now
        self.provider = provider or DisconnectedProvider()

    def handle(self, text: str) -> str:
        normalized = ' '.join(re.sub(r'[^\w\s]', ' ', text.lower().replace('ё', 'е')).split())
        if not normalized:
            return 'Речь не распознана. Попробуйте записать команду ещё раз.'
        if normalized in {'привет', 'здравствуй', 'здравствуйте'}:
            return 'Привет! Я Eidos. Скажите «Помощь», чтобы узнать доступные команды.'
        if normalized in {'который час', 'сколько времени', 'время'}:
            return f'Сейчас {self.now():%H:%M}.'
        if normalized in {'какая сегодня дата', 'какое сегодня число', 'дата'}:
            today = self.now()
            return f'Сегодня {today.day} {self.MONTHS[today.month - 1]} {today.year} года.'
        if normalized in {'помощь', 'команды', 'что ты умеешь'}:
            return 'Доступные команды: «Привет», «Который час?», «Какая сегодня дата?», «Помощь».'
        return self.provider.respond(text)
