"""Window snapshots and atomic persistence stay off the GUI event loop."""
from threading import Event
from PyQt6.QtCore import QThread, pyqtSignal


class SessionMonitor(QThread):
    failed = pyqtSignal(str)
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.stop_event, self.snapshot_event = Event(), Event()
        self.setObjectName('EidosSessionMonitor')

    def snapshot(self):
        self.snapshot_event.set()

    def stop(self):
        self.stop_event.set()
        self.snapshot_event.set()

    def run(self):
        while not self.stop_event.is_set():
            requested = self.snapshot_event.wait(15)
            self.snapshot_event.clear()
            try:
                self.service.desktop.sessions.save(changed_only=not requested and not self.stop_event.is_set())
            except Exception:
                self.failed.emit('Не удалось сохранить снимок рабочей сессии')
