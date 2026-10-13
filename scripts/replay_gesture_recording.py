"""Replay the explicit native test recording through current logic, no OS actions."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
from eidos.modules.vision.detector import HandDetector
from eidos.modules.vision.logic import GestureEngine

source = Path("docs/gestures/recording/camera-preview.mp4")
capture = cv2.VideoCapture(str(source))
assert capture.isOpened()
fps = capture.get(cv2.CAP_PROP_FPS)
detector = HandDetector(Path(".cache/gesture-model/hand_landmarker.task"))
engine = GestureEngine()
counts = {k: 0 for k in ("volume", "media", "cursor")}
actions = []
n = 0
try:
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        # Recorded preview was mirrored. Restore original camera orientation.
        rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        t = n / fps
        hand = detector.detect(rgb, t, "Right")
        from eidos.modules.vision.logic import classify

        kind = classify(hand)
        if kind:
            counts[kind] += 1
        action = engine.step(hand, t)
        if action:
            actions.append({"time": t, "kind": action.kind, "value": action.value})
        n += 1
finally:
    detector.close()
    capture.release()
report = {
    "source": str(source),
    "frames": n,
    "fps": fps,
    "recognized_frames": counts,
    "actions": actions,
    "os_actions_executed": False,
}
Path("docs/gestures/recording/replay.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    {
        "frames": n,
        "counts": counts,
        "actions": {k: sum(a["kind"] == k for a in actions) for k in counts},
    }
)
