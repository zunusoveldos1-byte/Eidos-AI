"""Modern MediaPipe Tasks adapter. Imported only when camera starts."""

import math
from .logic import Hand


class HandDetector:
    def __init__(self, path):
        import mediapipe as mp

        self.mp = mp
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=path.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.7,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self.previous = None
        self.last_ms = -1

    def detect(self, rgb, timestamp, side):
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        stamp = max(self.last_ms + 1, int(timestamp * 1000))
        self.last_ms = stamp
        result = self.detector.detect_for_video(image, stamp)
        candidates = []
        height, width = rgb.shape[:2]
        for p, categories in zip(result.hand_landmarks, result.handedness):
            category = categories[0]
            # MediaPipe Tasks handedness for unmirrored input is passed unchanged.
            if category.category_name != side or category.score < 0.7:
                continue
            if any(
                not 0.01 < point.x < 0.99 or not 0.01 < point.y < 0.99 for point in p
            ):
                continue
            points = tuple((v.x, v.y * height / width, v.z) for v in p)
            candidates.append(Hand(points, side, category.score, (p[8].x, p[8].y)))
        if not candidates:
            self.previous = None
            return None
        if self.previous is None:
            selected = max(candidates, key=lambda h: h.confidence)
        else:
            selected = min(
                candidates, key=lambda h: math.dist(h.points[0], self.previous)
            )
            if math.dist(selected.points[0], self.previous) > 0.2:
                self.previous = None
                return None
        self.previous = selected.points[0]
        return selected

    def reset(self):
        self.previous = None

    def close(self):
        self.detector.close()
