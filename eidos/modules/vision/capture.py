"""Only owner of VideoCapture. Keeps one newest frame; never emits images."""

import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal


class CameraDiscovery(QThread):
    discovered = pyqtSignal(object)
    failed = pyqtSignal(str)

    def stop(self):
        self.requestInterruption()

    def run(self):
        try:
            import cv2
            from cv2_enumerate_cameras import enumerate_cameras

            devices = enumerate_cameras(cv2.CAP_MSMF)
            if not self.isInterruptionRequested():
                self.discovered.emit(devices)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(
                    "Список OpenCV камер недоступен. Установите зависимости gestures: "
                    + str(exc)
                )


class CameraCapture(QThread):
    status = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, slot, camera, width, height, parent=None, factory=None):
        super().__init__(parent)
        self.slot, self.camera, self.width, self.height = slot, camera, width, height
        self.stop_event = threading.Event()
        self.factory = factory

    def stop(self):
        self.stop_event.set()

    def run(self):
        capture = None
        try:
            import cv2

            self.status.emit("Включаю камеру…")
            capture = (
                self.factory()
                if self.factory
                else cv2.VideoCapture(self.camera, cv2.CAP_MSMF)
            )
            if not capture.isOpened():
                raise RuntimeError(
                    "Камера недоступна: проверьте доступ Windows и закройте другие приложения камеры"
                )
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            failures = 0
            first = True
            while not self.stop_event.is_set():
                ok, frame = capture.read()
                if not ok or frame is None:
                    failures += 1
                    if failures >= 10:
                        raise RuntimeError(
                            "Камера перестала отдавать кадры. Проверьте USB и доступ к устройству"
                        )
                    self.stop_event.wait(0.05)
                    continue
                failures = 0
                if first:
                    self.status.emit("● Камера включена · локальная обработка")
                    first = False
                self.slot.put((frame.copy(), time.perf_counter()))
        except Exception as exc:
            self.failed.emit(f"Не удалось получить видео: {exc}")
        finally:
            if capture is not None:
                capture.release()
            self.slot.take()
