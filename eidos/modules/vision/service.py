"""Single camera service implementing GestureProvider; Qt GUI polls bounded slots."""

from dataclasses import dataclass
import threading
import time

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage

from .runtime import Latest, ControlGate
from .logic import GestureEngine, GestureSettings
from .capture import CameraCapture, CameraDiscovery
from .model import ensure_model

CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (0, 17),
    (17, 18),
    (18, 19),
    (19, 20),
)


def frame_image(frame, mirror, hand=None, overlay=True):
    import cv2

    # A new contiguous buffer, then QImage.copy() gives Qt owned memory.
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    if overlay and hand:
        points = [(round(x * w), round(y * w)) for x, y, z in hand.points]
        for a, b in CONNECTIONS:
            cv2.line(rgb, points[a], points[b], (47, 224, 155), 2)
        for p in points:
            cv2.circle(rgb, p, 4, (250, 250, 250), -1)
    if mirror:
        rgb = cv2.flip(rgb, 1)
    return QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()


@dataclass(frozen=True)
class GestureResult:
    image: QImage
    hand: object
    gesture: str | None
    fps: float
    latency_ms: float
    action: str
    volume: float | None
    timestamp: float


class HandWorker(QThread):
    status = pyqtSignal(str)
    ready = pyqtSignal()
    failed = pyqtSignal(str)
    action_failed = pyqtSignal(str)

    def __init__(
        self,
        frames,
        results,
        gate,
        model_dir,
        fps,
        overlay=True,
        parent=None,
        detector_factory=None,
        executor_factory=None,
        model_loader=ensure_model,
    ):
        super().__init__(parent)
        self.frames, self.results, self.gate = frames, results, gate
        self.model_dir, self.fps, self.overlay = model_dir, fps, overlay
        self.stop_event = threading.Event()
        self.detector_factory, self.executor_factory = (
            detector_factory,
            executor_factory,
        )
        self.model_loader = model_loader

    def stop(self):
        self.stop_event.set()

    def run(self):
        detector = executor = None
        try:
            from .detector import HandDetector
            from .actions import WindowsActions
            import cv2

            if self.detector_factory is None:
                import mediapipe  # Check dependency before attempting a download.
            path = self.model_loader(self.model_dir, self.stop_event, self.status.emit)
            if self.stop_event.is_set():
                return
            self.status.emit("Запускаю распознавание руки…")
            detector = (self.detector_factory or HandDetector)(path)
            self.ready.emit()
            engine = None
            previous_generation = -1
            last_stamp = -1
            last_action = "Управление выключено"
            volume = None
            volume_at = -10.0
            completed = []
            while not self.stop_event.is_set():
                start = time.perf_counter()
                settings, enabled, generation = self.gate.snapshot()
                if generation != previous_generation:
                    engine = GestureEngine(settings)
                    detector.reset()
                    previous_generation = generation
                    last_action = (
                        "Управление включено" if enabled else "Управление выключено"
                    )
                item = self.frames.peek()
                if item is None or start - item[1] > 0.25:
                    engine.lose_hand(start)
                    detector.reset()
                    self.stop_event.wait(0.01)
                    continue
                if item[1] == last_stamp:
                    self.stop_event.wait(0.005)
                    continue
                frame, stamp = item
                last_stamp = stamp
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hand = detector.detect(rgb, stamp, settings.hand)
                now = time.perf_counter()
                fresh = now - stamp <= 0.25
                if not fresh:
                    hand = None
                action = engine.step(hand, now) if enabled else None
                if not enabled:
                    engine.reset()
                if enabled and executor is None:
                    executor = (self.executor_factory or WindowsActions)()
                if action is not None:
                    try:
                        message = self.gate.execute(
                            generation,
                            action,
                            executor,
                            fresh=fresh and not self.stop_event.is_set(),
                        )
                        if message:
                            last_action = message
                    except Exception as exc:
                        self.gate.configure(settings, False)
                        engine.reset()
                        last_action = "Управление отключено: " + str(exc)
                        self.action_failed.emit(last_action)
                # Read volume in its COM owner, even in preview-only mode.
                if now - volume_at >= 1:
                    volume_at = now
                    try:
                        if executor is None:
                            executor = (self.executor_factory or WindowsActions)()
                        volume = executor.volume()
                    except Exception:
                        volume = None
                completed.append(now)
                completed = [t for t in completed if now - t <= 2]
                fps = (
                    (len(completed) - 1) / (completed[-1] - completed[0])
                    if len(completed) > 1
                    else 0.0
                )
                from .logic import classify

                result = GestureResult(
                    frame_image(frame, settings.mirror, hand, self.overlay),
                    hand,
                    classify(hand),
                    fps,
                    (now - stamp) * 1000,
                    last_action,
                    volume,
                    stamp,
                )
                self.results.put(result)
                self.stop_event.wait(
                    max(0, 1 / self.fps - (time.perf_counter() - start))
                )
        except InterruptedError:
            pass
        except Exception as exc:
            self.failed.emit(
                "Распознавание недоступно: "
                + str(exc)
                + ". Предпросмотр продолжает работать; выключите и включите камеру для повтора."
            )
        finally:
            for resource in (detector, executor):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:
                        pass


class CameraGestureService(QObject):
    status_changed = pyqtSignal(str)
    recognition_status = pyqtSignal(str)
    frame_ready = pyqtSignal(QImage)
    result_ready = pyqtSignal(object)
    ready = pyqtSignal()
    stopped = pyqtSignal()
    control_failed = pyqtSignal(str)
    cameras_ready = pyqtSignal(object)
    _retained = set()

    def __init__(
        self,
        model_dir,
        parent=None,
        capture_factory=CameraCapture,
        worker_factory=HandWorker,
    ):
        super().__init__(parent)
        self.model_dir = model_dir
        self.capture_factory, self.worker_factory = capture_factory, worker_factory
        self.frames, self.results = Latest(), Latest()
        self.gate = ControlGate()
        self.gate.configure(GestureSettings(), False)
        self.capture = self.worker = self.discovery = None
        self.latest = None
        self.recognition_ready = False
        self._stopping = False
        self.closed = False
        self.timer = QTimer(self)
        self.timer.setInterval(66)
        self.timer.timeout.connect(self._poll)

    @property
    def is_running(self):
        return any(
            t is not None and t.isRunning()
            for t in (self.capture, self.worker, self.discovery)
        )

    def discover(self):
        if self.closed or self.is_running or self._stopping:
            return
        if self.discovery is not None:
            self.discovery.deleteLater()
        self.discovery = CameraDiscovery(self)
        self.discovery.discovered.connect(self.cameras_ready)
        self.discovery.failed.connect(self.status_changed)
        self.discovery.finished.connect(self._discovery_finished)
        self._retained.add(self)
        self.discovery.start()

    def _discovery_finished(self):
        if self._stopping:
            self._finished()
        elif not self.is_running:
            self._retained.discard(self)

    def start(
        self, camera=0, width=640, height=480, fps=15, settings=None, overlay=True
    ):
        if self.closed or self.is_running or self._stopping:
            return
        self.latest = None
        self.recognition_ready = False
        self.gate.configure(settings or GestureSettings(), False)
        self.capture = self.capture_factory(self.frames, camera, width, height, self)
        self.worker = self.worker_factory(
            self.frames, self.results, self.gate, self.model_dir, fps, overlay, self
        )
        self.capture.status.connect(self.status_changed)
        self.capture.failed.connect(self._camera_failed)
        self.worker.status.connect(self.recognition_status)
        self.worker.failed.connect(self._recognition_failed)
        self.worker.action_failed.connect(self._action_failed)
        self.worker.ready.connect(self._ready)
        self.capture.finished.connect(self._finished)
        self.worker.finished.connect(self._finished)
        self._retained.add(self)
        self.capture.start()
        self.worker.start()
        self.timer.start()

    def configure(self, settings, enabled=False):
        if enabled and (self.closed or not self.recognition_ready or self._stopping):
            enabled = False
        self.gate.configure(settings, enabled)
        # Clear cached result immediately when permission changes.
        self.results.take()
        self.latest = None
        return enabled

    def _ready(self):
        if self._stopping:
            return
        self.recognition_ready = True
        self.recognition_status.emit(
            "Распознавание работает локально · покажите ведущую руку целиком"
        )
        self.ready.emit()

    def _camera_failed(self, message):
        self.stop()
        self.status_changed.emit(message)

    def _recognition_failed(self, message):
        self.recognition_ready = False
        settings, _, _ = self.gate.snapshot()
        self.configure(settings, False)
        self.recognition_status.emit(message)
        self.control_failed.emit(message)

    def _action_failed(self, message):
        self.control_failed.emit(message)

    def _poll(self):
        if self._stopping:
            return
        result = self.results.take()
        if result is not None and time.perf_counter() - result.timestamp <= 0.3:
            self.latest = result
            self.frame_ready.emit(result.image)
            self.result_ready.emit(result)
        elif self.capture and self.capture.isRunning():
            item = self.frames.peek()
            if item is not None and time.perf_counter() - item[1] <= 0.3:
                settings, _, _ = self.gate.snapshot()
                self.frame_ready.emit(frame_image(item[0], settings.mirror))
            elif self.latest is not None:
                self.latest = None
                self.recognition_status.emit("Нет свежего кадра · действия остановлены")

    def poll_gesture(self):
        return (
            self.latest.gesture
            if self.latest is not None
            and time.perf_counter() - self.latest.timestamp <= 0.3
            else None
        )

    def stop(self):
        settings, _, _ = self.gate.snapshot()
        self.configure(settings, False)
        self.recognition_ready = False
        self._stopping = True
        self.timer.stop()
        for t in (self.capture, self.worker, self.discovery):
            if t is not None:
                t.stop()
        self.status_changed.emit("Камера выключена · освобождаю устройство…")
        self._finished()

    def shutdown(self):
        self.closed = True
        self.stop()

    def _finished(self):
        if self.is_running:
            return
        if not self._stopping:
            return  # Model error can leave capture running.
        for name in ("capture", "worker", "discovery"):
            t = getattr(self, name)
            if t is not None:
                t.deleteLater()
                setattr(self, name, None)
        self.frames.take()
        self.results.take()
        self.latest = None
        self._stopping = False
        self.status_changed.emit("Камера выключена")
        self.stopped.emit()
        self._retained.discard(self)
