import threading
from dataclasses import replace

import pytest
from test_ui import app
from eidos.modules.vision.runtime import Latest, ControlGate
from eidos.modules.vision.logic import Action


def test_latest_replaces_frames_instead_of_building_queue():
    slot = Latest()
    for n in range(100):
        slot.put(n)
    assert slot.take() == 99
    assert slot.take() is None


class FakeActions:
    def __init__(self):
        self.calls = []

    def execute(self, action):
        self.calls.append(action)
        return "ok"


def test_gate_revokes_stale_detection_and_explicit_disable():
    gate = ControlGate()
    actions = FakeActions()
    gate.configure("a", True)
    old = gate.snapshot()[2]
    gate.configure("a", False)
    assert gate.execute(old, Action("media"), actions) is None
    gate.configure("a", True)
    assert gate.execute(old, Action("volume", 50), actions) is None
    assert gate.execute(gate.snapshot()[2], Action("media"), actions) == "ok"
    assert len(actions.calls) == 1


def test_gate_blocks_commands_from_stale_frames():
    gate = ControlGate()
    gate.configure("a", True)
    actions = FakeActions()
    assert (
        gate.execute(gate.snapshot()[2], Action("cursor", (0, 0)), actions, fresh=False)
        is None
    )
    assert not actions.calls


def test_qimage_owns_memory_and_mirror_direction():
    import numpy as np
    from eidos.modules.vision.service import frame_image

    frame = np.zeros((30, 40, 3), dtype=np.uint8)
    frame[:, 0] = (0, 0, 255)
    image = frame_image(frame, True)
    frame[:] = 255
    assert image.pixelColor(39, 10).red() == 255
    assert image.pixelColor(0, 10).red() == 0


def test_model_checksum_rejects_corrupt_file_and_cancel_cleans_download(
    tmp_path, monkeypatch
):
    import hashlib, io
    from eidos.modules.vision import model

    data = b"valid model"
    monkeypatch.setattr(model, "SIZE", len(data))
    monkeypatch.setattr(model, "SHA256", hashlib.sha256(data).hexdigest())
    path = tmp_path / "hand_landmarker.task"
    path.write_bytes(b"wrong model")
    assert not model.verified(path)
    monkeypatch.setattr(
        model.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(data)
    )
    stop = threading.Event()
    stop.set()
    with pytest.raises(InterruptedError):
        model.ensure_model(tmp_path, stop, lambda _: None)
    assert not list(tmp_path.glob("*.download"))
    stop.clear()
    assert model.ensure_model(tmp_path, stop, lambda _: None) == path
    assert model.verified(path)


def test_capture_releases_device_even_on_disconnect(app):
    import numpy as np
    from eidos.modules.vision.capture import CameraCapture
    from test_ui import wait_until

    class Capture:
        def __init__(self):
            self.released = False
            self.n = 0

        def isOpened(self):
            return True

        def set(self, *a):
            pass

        def read(self):
            self.n += 1
            return (
                (True, np.zeros((20, 20, 3), dtype=np.uint8))
                if self.n == 1
                else (False, None)
            )

        def release(self):
            self.released = True

    capture = Capture()
    slot = Latest()
    worker = CameraCapture(slot, 0, 640, 480, factory=lambda: capture)
    errors = []
    worker.failed.connect(errors.append)
    worker.start()
    wait_until(app, lambda: not worker.isRunning() and bool(errors))
    assert capture.released and slot.peek() is None
    assert errors


def test_revocation_during_detection_never_executes_stale_action(app, tmp_path):
    import time, numpy as np
    from test_gestures import hand
    from test_ui import wait_until
    from eidos.modules.vision.service import HandWorker
    from eidos.modules.vision.logic import GestureSettings

    frames, results = Latest(), Latest()
    gate = ControlGate()
    gate.configure(replace(GestureSettings(), stability=0), True)
    entered, release = threading.Event(), threading.Event()

    class Detector:
        def __init__(self, p):
            pass

        def reset(self):
            pass

        def detect(self, *a):
            entered.set()
            release.wait(2)
            return hand("volume")

        def close(self):
            pass

    class Executor(FakeActions):
        def volume(self):
            return 50

        def close(self):
            pass

    executor = Executor()
    worker = HandWorker(
        frames,
        results,
        gate,
        tmp_path,
        15,
        detector_factory=Detector,
        executor_factory=lambda: executor,
        model_loader=lambda *a: tmp_path / "mock",
    )
    ready = []
    worker.ready.connect(lambda: ready.append(True))
    worker.start()
    try:
        wait_until(app, lambda: bool(ready), timeout=10)
        frames.put((np.zeros((40, 40, 3), dtype=np.uint8), time.perf_counter()))
        wait_until(app, entered.is_set, timeout=10)
        gate.configure(GestureSettings(), False)
        release.set()
        wait_until(app, lambda: results.peek() is not None)
        assert not executor.calls
    finally:
        release.set()
        worker.stop()
        wait_until(app, lambda: not worker.isRunning())
