from typing import Protocol
from eidos.agent.harness import TaskContext, ToolResult


class CalendarProvider(Protocol):
    """A future external adapter must use the same confirmed tool registry."""
    def list(self) -> list[dict]: ...
    def change(self, arguments: dict, context: TaskContext) -> ToolResult: ...


class ExternalCalendarUnavailable:
    def list(self):
        raise RuntimeError('Внешний календарь пока не реализован. Используйте локальный календарь.')

    def change(self, arguments, context):
        raise RuntimeError('Внешняя синхронизация календаря не подключена')
