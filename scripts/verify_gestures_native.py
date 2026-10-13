"""Explicit diagnostic run. Reads camera locally; uses fake action executors.

No video is recorded by default. --record opts into a short local preview recording.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QWidget
from eidos.modules.vision.actions import monitors, WindowsActions
from eidos.modules.vision.logic import GestureSettings
from eidos.modules.vision.model import ensure_model
from eidos.modules.vision.service import CameraGestureService
from eidos.ui.hotkeys import GestureEmergencyHotkey
from eidos.core.config import AppConfig


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--output", default="docs/gestures/native")
    args = parser.parse_args()
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    owner = QWidget()
    import cv2
    from cv2_enumerate_cameras import enumerate_cameras

    devices = enumerate_cameras(cv2.CAP_MSMF)
    report = {
        "cameras": [{"index": c.index, "name": c.name} for c in devices],
        "monitors": [asdict(m) for m in monitors()],
        "system_actions": "mocked",
        "video_recorded": args.record,
    }
    # Verify real RegisterHotKey and WM_HOTKEY delivery with the owner unfocused.
    hotkey = GestureEmergencyHotkey(owner)
    report["global_hotkey_registered"] = (
        hotkey.configure(AppConfig()) and hotkey.available
    )
    hotkey_events = []
    hotkey.activated.connect(hotkey_events.append)
    if report["global_hotkey_registered"]:
        import ctypes
        from ctypes import wintypes

        user = ctypes.windll.user32
        report["owner_unfocused"] = user.GetForegroundWindow() != int(owner.winId())
        identifier = next(iter(hotkey.actions))
        # Posts WM_HOTKEY: tests native event routing, not physical keyboard input.
        user.PostThreadMessageW(
            ctypes.windll.kernel32.GetCurrentThreadId(), 0x0312, identifier, 0
        )
        deadline = time.perf_counter() + 1
        while not hotkey_events and time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.005)
    report["native_hotkey_dispatch"] = hotkey_events == ["gesture_stop"]
    hotkey.shutdown()
    actions = WindowsActions()
    try:
        report["system_volume_read_percent"] = actions.volume()
    except Exception as exc:
        report["system_volume_read_error"] = str(exc)
    finally:
        actions.close()
    if not devices:
        report["camera_test"] = "No device"
        (directory / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=True))
        return
    import threading

    model_path = ensure_model(
        Path(".cache/gesture-model"), threading.Event(), lambda s: print(s, flush=True)
    )
    service = CameraGestureService(model_path.parent, owner)
    from eidos.modules.vision.service import HandWorker

    calls = []

    class FakeActions:
        def execute(self, a):
            calls.append({"kind": a.kind, "value": a.value})
            return "TEST: " + a.kind

        def volume(self):
            return report.get("system_volume_read_percent", 0)

        def close(self):
            pass

    service.worker_factory = lambda *a: HandWorker(*a, executor_factory=FakeActions)
    results = []
    errors = []
    images = []
    recording = None
    service.result_ready.connect(results.append)
    service.status_changed.connect(lambda s: errors.append(s))
    service.recognition_status.connect(lambda s: errors.append(s))

    def frame(image):
        nonlocal recording
        images[:] = [image]
        if args.record:
            import numpy as np

            if recording is None:
                recording = cv2.VideoWriter(
                    str(directory / "camera-preview.mp4"),
                    cv2.VideoWriter_fourcc(*"mp4v"),
                    15,
                    (image.width(), image.height()),
                )
            buffer = image.bits()
            buffer.setsize(image.sizeInBytes())
            rgb = (
                np.frombuffer(buffer, dtype=np.uint8)
                .reshape(image.height(), image.bytesPerLine())[:, : image.width() * 3]
                .reshape(image.height(), image.width(), 3)
            )
            recording.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

    service.frame_ready.connect(frame)

    def allow_test_actions():
        service.configure(GestureSettings(), True)

    service.ready.connect(allow_test_actions)  # fake executor only
    service.start(devices[0].index, 640, 480, 15, GestureSettings())
    deadline = time.perf_counter() + args.seconds
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.005)
    shutdown = time.perf_counter()
    service.shutdown()
    while service.is_running and time.perf_counter() - shutdown < 12:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    if recording:
        recording.release()
    if images and args.record:
        images[0].save(str(directory / "camera-preview.png"))
    report.update(
        processed_frames=len(results),
        hand_frames=sum(r.hand is not None for r in results),
        gestures={
            name: sum(r.gesture == name for r in results)
            for name in ("volume", "media", "cursor")
        },
        fake_action_calls=calls,
        statuses=errors,
        shutdown_seconds=time.perf_counter() - shutdown,
        workers_stopped=not service.is_running,
    )
    if results:
        ms = [r.latency_ms for r in results]
        fps = [r.fps for r in results if r.fps]
        report.update(
            latency_ms_mean=statistics.mean(ms),
            latency_ms_p95=sorted(ms)[int(0.95 * (len(ms) - 1))],
            processing_fps_mean=statistics.mean(fps) if fps else 0,
        )
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=True), flush=True)
    if service.is_running:
        # Do not destroy a running native capture. Wait cooperatively.
        service.stopped.connect(app.quit)
        app.exec()


if __name__ == "__main__":
    main()
