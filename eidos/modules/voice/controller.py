"""GUI-thread lifecycle coordinator; blocking engines run in VoiceWorker."""

from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from eidos.core.config import AppConfig
from eidos.core.state import State, StateMachine
from .playback import AudioPlayback
from .worker import VoiceWorker


class VoiceController(QObject):
    state_changed = pyqtSignal(str, str)
    transcript = pyqtSignal(str)
    reply = pyqtSignal(str)
    log_event = pyqtSignal(str)
    devices = pyqtSignal(object)
    devices_error = pyqtSignal(str)
    agent_progress = pyqtSignal(str, str)
    closed = pyqtSignal()
    level = pyqtSignal(float)
    start_requested = pyqtSignal(object, object)
    devices_requested = pyqtSignal()

    def __init__(self, cache: Path, parent: QObject | None = None,
                 worker: VoiceWorker | None = None) -> None:
        super().__init__(parent)
        self.cache = cache
        self.machine = StateMachine()
        self.active = False
        self.discovering = False
        self.cancelling = False
        self.thread = QThread(self)
        self.worker = worker or VoiceWorker()
        self.worker.moveToThread(self.thread)
        self.playback = AudioPlayback(self)
        self.start_requested.connect(self.worker.run_cycle)
        self.devices_requested.connect(self.worker.refresh_devices)
        self.worker.progress.connect(self._progress)
        self.worker.transcript.connect(self._transcript)
        self.worker.reply.connect(self._reply)
        self.worker.audio.connect(self._audio)
        self.worker.error.connect(self._error)
        self.worker.finished.connect(self._finished)
        self.worker.devices.connect(self._devices)
        self.worker.devices_error.connect(self._devices_error)
        self.worker.agent_progress.connect(self.agent_progress)
        self.worker.level.connect(self.level)
        self.playback.finished.connect(self._playback_finished)
        self.playback.error.connect(self._error)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    @property
    def closing(self) -> bool:
        return self.machine.state == State.CLOSING

    def _set_state(self, state: State, message: str) -> None:
        if self.machine.state != state:
            self.machine.transition(state)
        self.state_changed.emit(state.value, message)
        self.log_event.emit(message)

    def start(self, config: AppConfig) -> None:
        if self.closing or self.active or self.discovering or self.playback.active:
            return
        config.validate()
        if self.machine.state == State.ERROR:
            self.machine.transition(State.IDLE)
        self.cancelling = False
        self.worker.stop_event.clear()
        self.worker.cancel_event.clear()
        self.active = True
        self._set_state(State.STARTING, 'Открытие микрофона…')
        self.start_requested.emit(config, self.cache)

    def stop(self) -> None:
        if self.closing:
            return
        if self.machine.state in {State.STARTING, State.RECORDING}:
            self.worker.stop_event.set()
            self.state_changed.emit(self.machine.state.value, 'Остановка записи…')
        elif self.playback.active:
            self.playback.stop()
            self._set_state(State.IDLE, 'Воспроизведение остановлено.')
        elif self.active:
            self.cancelling = True
            self.worker.cancel_event.set()
            self.state_changed.emit(self.machine.state.value, 'Отмена… Ожидание текущей операции.')

    def refresh_devices(self) -> None:
        if self.closing or self.active or self.discovering or self.playback.active:
            return
        self.discovering = True
        self.devices_requested.emit()

    @pyqtSlot(str, str)
    def _progress(self, state: str, message: str) -> None:
        if not self.closing and not self.cancelling:
            self._set_state(State(state), message)

    @pyqtSlot(str)
    def _transcript(self, text: str) -> None:
        if not self.closing and not self.cancelling:
            self.transcript.emit(text)

    @pyqtSlot(str)
    def _reply(self, text: str) -> None:
        if not self.closing and not self.cancelling:
            self.reply.emit(text)

    @pyqtSlot(object)
    def _audio(self, path: Path) -> None:
        if self.closing or self.cancelling:
            path.unlink(missing_ok=True)
            return
        self._set_state(State.PLAYING, 'Воспроизведение ответа…')
        self.playback.play(path)

    @pyqtSlot(str)
    def _error(self, message: str) -> None:
        if not self.closing:
            self._set_state(State.ERROR, message)

    @pyqtSlot()
    def _finished(self) -> None:
        self.active = False
        if self.closing:
            return
        cancelled = self.cancelling
        self.cancelling = False
        if cancelled:
            self._set_state(State.IDLE, 'Обработка отменена. Можно начать новую запись.')
        elif self.machine.state == State.ERROR:
            # Keep the useful error message until the next explicit action.
            self.machine.transition(State.IDLE)
            self.state_changed.emit('idle', 'Ошибка. Можно повторить запись; подробности в журнале.')
        elif not self.playback.active:
            self._set_state(State.IDLE, 'Готово. Нажмите «Начать запись».')

    @pyqtSlot()
    def _playback_finished(self) -> None:
        if not self.closing:
            self._set_state(State.IDLE, 'Готово. Нажмите «Начать запись».')

    @pyqtSlot(object)
    def _devices(self, devices: object) -> None:
        self.discovering = False
        if not self.closing:
            self.devices.emit(devices)

    @pyqtSlot(str)
    def _devices_error(self, message: str) -> None:
        self.discovering = False
        if not self.closing:
            self.devices_error.emit(message)

    def shutdown(self) -> None:
        if self.closing:
            return
        self._set_state(State.CLOSING, 'Завершение… Ожидание текущей операции.')
        self.worker.cancel_event.set()
        self.worker.stop_event.set()
        self.playback.dispose()
        self.thread.quit()
        if not self.thread.isRunning():
            QTimer.singleShot(0, self.closed.emit)

    @pyqtSlot()
    def _thread_finished(self) -> None:
        if self.closing:
            self.closed.emit()
