from dataclasses import replace
import math

import pytest

from eidos.modules.vision.logic import (
    Hand,
    GestureEngine,
    GestureSettings,
    Monitor,
    classify,
    pinch_ratio,
    map_cursor,
    Smooth,
)


def hand(kind="media", scale=1, rotate=0, side="Right"):
    p = [(0.0, 0.0, 0.0)] * 21
    p[0] = (0.5, 0.85, 0)
    for i, x in [(5, 0.35), (9, 0.48), (13, 0.61), (17, 0.73)]:
        opened = kind == "media" or (i == 5 and kind in ("cursor", "volume"))
        p[i] = (x, 0.62, 0)
        p[i + 1] = (x, 0.45, 0)
        p[i + 2] = (x, 0.3 if opened else 0.54, 0)
        p[i + 3] = (x, 0.16 if opened else 0.68, 0)
    p[1], p[2], p[3], p[4] = (
        (0.38, 0.75, 0),
        (0.24, 0.64, 0),
        (0.15, 0.53, 0),
        (0.06, 0.42, 0),
    )
    if kind == "cursor":
        p[3], p[4] = (0.32, 0.7, 0), (0.45, 0.74, 0)
    c, s = math.cos(rotate), math.sin(rotate)
    points = tuple(
        (scale * (x * c - y * s), scale * (x * s + y * c), z * scale) for x, y, z in p
    )
    return Hand(points, side, 0.99)


@pytest.mark.parametrize("kind", ["volume", "cursor", "media"])
@pytest.mark.parametrize("rotation", [0, 0.7, 1.6, 3.14])
def test_joint_geometry_handles_rotation(kind, rotation):
    assert classify(hand(kind, rotate=rotation)) == kind


def test_pinch_normalization_and_volume_bounds():
    assert pinch_ratio(hand("volume")) == pytest.approx(
        pinch_ratio(hand("volume", scale=3))
    )
    e = GestureEngine(replace(GestureSettings(), stability=0, smoothing=1))
    assert e.volume(-1) == 0
    assert e.volume(100) == 100


def test_smoothing_and_dead_zone():
    s = Smooth(0.5, 2)
    assert s.update(50) == 50
    assert s.update(51) == 50
    assert s.update(70) == 60


def test_media_hold_one_shot_release_and_cooldown():
    e = GestureEngine(replace(GestureSettings(), stability=0, hold=0.5, cooldown=1.2))
    h = hand()
    assert e.step(h, 0) is None
    assert e.step(h, 0.49) is None
    assert e.step(h, 0.51).kind == "media"
    assert e.step(h, 2) is None
    e.step(None, 2.1)
    e.step(None, 2.31)
    assert e.step(h, 2.4) is None
    assert e.step(h, 3.0).kind == "media"


def test_cursor_negative_monitor_mirror_clamp():
    m = Monitor("left", -1920, -200, 1920, 1080)
    assert map_cursor((0.1, 0.1), m, False, 0.1) == (-1920, -200)
    assert map_cursor((0.1, 0.1), m, True, 0.1) == (-1, -200)
    assert map_cursor((2, 2), m, False, 0.1) == (-1, 879)


def test_manual_mode_conflict_and_loss_resets_filter():
    e = GestureEngine(
        replace(GestureSettings(), mode="cursor", stability=0, smoothing=1)
    )
    assert e.step(hand("volume"), 0) is None
    assert e.step(hand("media"), 1) is None
    assert e.step(hand("cursor"), 2).kind == "cursor"
    assert e.step(None, 3) is None
    assert e.active is None and e.cursor_x.value is None
    assert e.step(replace(hand("cursor"), confidence=0.1), 4) is None


def test_auto_waits_for_stability_and_never_conflicts():
    e = GestureEngine(GestureSettings())
    assert e.step(hand("cursor"), 0) is None
    assert e.step(hand("volume"), 0.1) is None
    assert e.step(hand("volume"), 0.2) is None
    assert e.step(hand("volume"), 0.4).kind == "volume"
    assert e.step(hand("cursor"), 0.41) is None


def test_partial_or_invalid_landmarks_are_rejected():
    assert classify(Hand(((0, 0, 0),), "Right", 1)) is None
    p = list(hand().points)
    p[8] = (float("nan"), 0, 0)
    assert classify(Hand(tuple(p), "Right", 1)) is None


def test_closed_pinch_does_not_become_cursor_and_ambiguous_thumb_is_ignored():
    p = list(hand("volume").points)
    p[4] = p[8]
    assert classify(Hand(tuple(p), "Right", 0.99)) == "volume"
    p[4] = (0.05, 0.3, 0)
    p[3] = (0.3, 0.7, 0)
    assert classify(Hand(tuple(p), "Right", 0.99)) is None


def test_short_uncertain_classification_does_not_rearm_held_palm():
    e = GestureEngine(replace(GestureSettings(), stability=0.2))
    h = hand()
    assert e.step(h, 0) is None
    assert e.step(h, 0.6).kind == "media"
    unknown = hand("cursor")
    p = list(unknown.points)
    p[8] = p[5]
    unknown = replace(unknown, points=tuple(p))
    assert classify(unknown) is None
    e.step(unknown, 2)
    e.step(h, 2.05)
    assert e.step(h, 2.6) is None


@pytest.mark.parametrize("dropout", [None, replace(hand(), confidence=0.1)])
def test_short_detection_gap_does_not_rearm_held_palm(dropout):
    e = GestureEngine(GestureSettings())
    h = hand()
    e.step(h, 0)
    assert e.step(h, 0.6).kind == "media"
    assert e.step(dropout, 2) is None
    assert e.active is None and e.cursor_x.value is None
    e.step(h, 2.05)
    assert e.step(h, 2.6) is None
