"""Pure gesture geometry and state. No camera, Qt or system side effects."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Hand:
    # Aspect-correct coordinates from the image. z is scaled by image width.
    points: tuple
    side: str
    confidence: float
    cursor_point: tuple | None = None


@dataclass(frozen=True)
class Monitor:
    name: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class GestureSettings:
    mode: str = "auto"
    hand: str = "Right"
    mirror: bool = True
    smoothing: float = 0.3  # EMA alpha; larger values respond faster
    sensitivity: float = 1.0
    pinch_min: float = 0.15
    pinch_max: float = 1.5
    volume_dead: float = 2.0
    volume_interval: float = 0.1
    hold: float = 0.5
    cooldown: float = 1.2
    stability: float = 0.2
    margin: float = 0.15
    confidence: float = 0.7
    monitor: Monitor = Monitor("primary", 0, 0, 1920, 1080)


@dataclass(frozen=True)
class Action:
    kind: str
    value: object = None


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def angle(a, b, c):
    u, v = tuple(x - y for x, y in zip(a, b)), tuple(x - y for x, y in zip(c, b))
    norm = distance(a, b) * distance(c, b)
    return (
        math.degrees(
            math.acos(max(-1, min(1, sum(x * y for x, y in zip(u, v)) / norm)))
        )
        if norm > 1e-8
        else 0
    )


def valid_hand(hand):
    return (
        hand is not None
        and len(hand.points) == 21
        and all(len(p) == 3 and all(math.isfinite(v) for v in p) for p in hand.points)
        and distance(hand.points[0], hand.points[9]) > 0.035
    )


def extended(p, i):
    return (
        angle(p[i], p[i + 1], p[i + 2]) > 155
        and angle(p[i + 1], p[i + 2], p[i + 3]) > 150
        and distance(p[0], p[i + 3]) > distance(p[0], p[i + 1]) * 1.08
    )


def classify(hand):
    if not valid_hand(hand):
        return None
    p = hand.points
    fingers = [extended(p, i) for i in (5, 9, 13, 17)]
    thumb = angle(p[1], p[2], p[3]) > 150 and angle(p[2], p[3], p[4]) > 150
    if all(fingers) and thumb:
        return "media"
    if fingers[0] and not any(fingers[1:]):
        # A closed pinch bends the thumb; it must not turn into a cursor gesture.
        if thumb or pinch_ratio(hand) < 0.45:
            return "volume"
        palm = (distance(p[0], p[9]) + distance(p[5], p[17])) / 2
        if (
            distance(p[4], p[9]) < palm * 0.65
            and min(angle(p[1], p[2], p[3]), angle(p[2], p[3], p[4])) < 140
        ):
            return "cursor"
    return None


def pinch_ratio(hand):
    p = hand.points
    palm = (distance(p[0], p[9]) + distance(p[5], p[17])) / 2
    return distance(p[4], p[8]) / max(palm, 1e-8)


def map_cursor(point, monitor, mirror, margin, sensitivity=1):
    x, y = point
    if mirror:
        x = 1 - x
    x = (x - margin) / (1 - 2 * margin)
    y = (y - margin) / (1 - 2 * margin)
    x, y = ((v - 0.5) * sensitivity + 0.5 for v in (x, y))
    return (
        monitor.x + round(max(0, min(1, x)) * (monitor.width - 1)),
        monitor.y + round(max(0, min(1, y)) * (monitor.height - 1)),
    )


class Smooth:
    def __init__(self, alpha, dead):
        self.alpha, self.dead, self.value = alpha, dead, None

    def update(self, value):
        if self.value is None:
            self.value = value
        elif abs(value - self.value) > self.dead:
            self.value += self.alpha * (value - self.value)
        return self.value


class GestureEngine:
    def __init__(self, settings=GestureSettings()):
        self.settings = settings
        self.last_media = -math.inf
        self.last_volume = -math.inf
        self.last_cursor = -math.inf
        self.last_sent_volume = None
        self.reset()

    def reset(self, keep_media=False):
        self.active = self.candidate = None
        self.since = 0.0
        self.palm_since = None
        if not keep_media:
            self.palm_latched = False
            self.release_since = None
        self.volume_filter = Smooth(self.settings.smoothing, self.settings.volume_dead)
        self.cursor_x = Smooth(self.settings.smoothing, 3)
        self.cursor_y = Smooth(self.settings.smoothing, 3)
        self.last_sent_volume = None

    def volume(self, ratio):
        s = self.settings
        return max(
            0.0, min(100.0, (ratio - s.pinch_min) / (s.pinch_max - s.pinch_min) * 100)
        )

    def lose_hand(self, now):
        # Stop motion and discard all coordinates immediately. Keep only the
        # one-shot media latch until disappearance is confirmed, so a single
        # missed detection cannot toggle playback a second time.
        if self.release_since is None:
            self.release_since = now
        if now - self.release_since >= max(0.15, self.settings.stability):
            self.palm_latched = False
        self.reset(keep_media=True)

    def step(self, hand, now):
        s = self.settings
        if (
            not valid_hand(hand)
            or hand.confidence < s.confidence
            or hand.side != s.hand
        ):
            self.lose_hand(now)
            return None
        kind = classify(hand)
        if kind != "media":
            self.palm_since = None
            if self.release_since is None:
                self.release_since = now
            if now - self.release_since >= max(0.15, s.stability):
                self.palm_latched = False
        else:
            self.release_since = None
        if kind is None or (s.mode != "auto" and s.mode != kind):
            self.reset(keep_media=True)
            return None
        if kind != self.candidate:
            self.candidate = kind
            self.since = now
            self.active = None
            self.volume_filter.value = self.cursor_x.value = self.cursor_y.value = None
            self.last_sent_volume = None
        if now - self.since < s.stability:
            return None
        self.active = kind
        if kind == "media":
            if self.palm_since is None:
                self.palm_since = self.since
            if (
                not self.palm_latched
                and now - self.palm_since >= s.hold
                and now - self.last_media >= s.cooldown
            ):
                self.palm_latched = True
                self.last_media = now
                return Action("media")
        elif kind == "volume":
            value = self.volume_filter.update(self.volume(pinch_ratio(hand)))
            if now - self.last_volume >= s.volume_interval and (
                self.last_sent_volume is None
                or abs(value - self.last_sent_volume) >= s.volume_dead
            ):
                self.last_volume = now
                self.last_sent_volume = value
                return Action("volume", value)
        elif kind == "cursor":
            # Input x/y is normalized to square image-width units; detector
            # records normalized image coordinates separately in worker mapping.
            point = hand.cursor_point or hand.points[8][:2]
            x, y = map_cursor(point, s.monitor, s.mirror, s.margin, s.sensitivity)
            x, y = round(self.cursor_x.update(x)), round(self.cursor_y.update(y))
            if now - self.last_cursor >= 1 / 30:
                self.last_cursor = now
                return Action("cursor", (x, y))
        return None
