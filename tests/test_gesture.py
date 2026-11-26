from types import SimpleNamespace

import numpy as np
import pytest

from animecam.tracking import GestureGate, gesture_geometry


def feed(gate, score, start, duration, step=0.025):
    return [gate.update(score, float(t)) for t in np.arange(start, start + duration, step)]


def test_hold_cooldown_release_and_second_trigger():
    gate = GestureGate()
    assert not any(s.triggered for s in feed(gate, 1, 0, 0.45))
    assert sum(s.triggered for s in feed(gate, 1, 0.45, 5)) == 1
    # Missing landmarks cannot unlatch a held pose.
    feed(gate, None, 5.45, 1)
    assert not any(s.triggered for s in feed(gate, 1, 6.45, 1))
    feed(gate, 0, 7.45, 0.5)
    assert sum(s.triggered for s in feed(gate, 1, 7.95, 1)) == 1


def test_pass_by_and_long_tracking_gap_reset_hold():
    gate = GestureGate()
    assert not any(s.triggered for s in feed(gate, 1, 0, 0.25))
    feed(gate, 0, 0.25, 0.2)
    assert not any(s.triggered for s in feed(gate, 1, 0.45, 0.25))
    feed(gate, None, 0.7, 0.4)
    assert not any(s.triggered for s in feed(gate, 1, 1.1, 0.4))


def test_short_occlusion_preserves_hold_without_counting_missing_time():
    gate = GestureGate()
    feed(gate, 1, 0, 0.3)
    statuses = feed(gate, None, 0.3, 0.1)
    assert statuses[-1].progress == pytest.approx(statuses[0].progress)
    assert not any(s.triggered for s in feed(gate, 1, 0.4, 0.15))
    assert any(s.triggered for s in feed(gate, 1, 0.55, 0.2))


def test_pipeline_stall_never_counts_as_a_stable_pose():
    gate = GestureGate()
    gate.update(1, 0)
    assert not gate.update(1, 10).triggered
    assert gate.update(1, 10.01).progress < 0.1


def landmarks(points):
    return [SimpleNamespace(x=float(x), y=float(y), z=0.0) for x, y in points]


def fixture_pose(scale=1.0, offset=(0, 0)):
    face = np.tile([0.5, 0.5], (478, 1))
    face[10], face[151], face[152] = [0.5, 0.25], [0.5, 0.32], [0.5, 0.75]
    face[234], face[454] = [0.3, 0.5], [0.7, 0.5]
    hand = np.tile([0.48, 0.6], (21, 1))
    hand[0] = [0.48, 0.65]
    for indices, x in (((5, 6, 7, 8), 0.48), ((9, 10, 11, 12), 0.52)):
        for i, y in zip(indices, (0.53, 0.45, 0.36, 0.285)):
            hand[i] = [x, y]
    for indices, x in (((13, 14, 15, 16), 0.55), ((17, 18, 19, 20), 0.58)):
        for i, y in zip(indices, (0.55, 0.48, 0.55, 0.60)):
            hand[i] = [x, y]
    return landmarks(hand * scale + offset), landmarks(face * scale + offset)


@pytest.mark.parametrize("scale,offset,width,height", [(1, (0, 0), 1280, 720),
    (0.5, (0.2, 0.1), 640, 480), (0.7, (0.1, 0.1), 1920, 1080)])
def test_geometry_is_normalized_to_face(scale, offset, width, height):
    hand, face = fixture_pose(scale, offset)
    assert gesture_geometry([hand], face, width, height).score > 0.9


def test_geometry_rejects_open_palm_distant_hand_and_missing_face():
    hand, face = fixture_pose()
    for i, y in zip((13, 14, 15, 16), (0.53, 0.45, 0.36, 0.285)):
        hand[i].y = y
    assert gesture_geometry([hand], face, 1280, 720).score == 0
    hand, face = fixture_pose()
    for p in hand:
        p.x += 0.4
    assert gesture_geometry([hand], face, 1280, 720).score == 0
    assert gesture_geometry([hand], None, 1280, 720).score is None
    assert gesture_geometry([], face, 1280, 720).score == 0


def test_geometry_accepts_head_roll():
    hand, face = fixture_pose()
    theta = np.deg2rad(25)
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    # Rotate in pixel coordinates to keep the camera's non-square aspect ratio.
    for collection in (hand, face):
        for p in collection:
            point = rotation @ (np.array([p.x * 1280, p.y * 720]) - [640, 360]) + [640, 360]
            p.x, p.y = point / [1280, 720]
    assert gesture_geometry([hand], face, 1280, 720).score > 0.9
