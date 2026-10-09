from typing import Protocol


class GestureProvider(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def poll_gesture(self) -> str | None: ...


class DisconnectedVision:
    status = 'Модуль пока не подключён'

    def start(self) -> None:
        raise NotImplementedError(self.status)

    def stop(self) -> None:
        pass

    def poll_gesture(self) -> str | None:
        return None
