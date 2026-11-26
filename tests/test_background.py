import numpy as np

from animecam.background import Background, replace_person
from animecam.segmentation import MaskSmoother


def auto_tick(bg, now, frame=None, mask=None, tracked=False, enabled=True, fresh=True):
    frame = np.full((90, 160, 3), 100, np.uint8) if frame is None else frame
    mask = np.zeros((90, 160), np.float32) if mask is None else mask
    bg.update_auto(frame, mask, now, tracked, enabled, fresh)
    return bg.update_capture(frame, mask, now, tracked)


def test_auto_capture_requires_continuous_empty_stable_scene_and_saves_only_once():
    bg = Background()
    captured = [t for t in np.arange(0, 5, 0.1) if auto_tick(bg, float(t))]
    assert len(captured) == 1 and captured[0] >= 3
    assert bg.image is not None and not bg.auto_armed
    original = bg.image.copy()
    for t in np.arange(5, 10, 0.1):
        auto_tick(bg, float(t), frame=np.full_like(original, 180))
    np.testing.assert_array_equal(bg.image, original)


def test_auto_never_captures_detected_face_hand_or_segmented_person():
    bg = Background()
    for t in np.arange(0, 4, 0.1):
        auto_tick(bg, float(t), tracked=True)  # face/hand present, even with failed mask
    assert bg.image is None and not bg.pending
    for t in np.arange(4, 8, 0.1):
        auto_tick(bg, float(t), mask=np.ones((90, 160), np.float32))  # back turned
    assert bg.image is None and not bg.pending
    weak_person = np.zeros((90, 160), np.float32)
    weak_person[20:40, 60:80] = 0.2
    for t in np.arange(8, 12, 0.1):
        auto_tick(bg, float(t), mask=weak_person)
    assert bg.image is None and not bg.pending


def test_auto_resets_if_person_returns_during_hold_or_frame_averaging():
    bg = Background()
    for t in np.arange(0, 1.6, 0.1):
        auto_tick(bg, float(t))
    auto_tick(bg, 1.6, tracked=True)
    for t in np.arange(1.7, 3.3, 0.1):
        auto_tick(bg, float(t))
    assert bg.image is None and not bg.pending
    for t in np.arange(3.3, 4.1, 0.1):
        auto_tick(bg, float(t))
    assert bg.pending and bg.image is None
    auto_tick(bg, 4.1, tracked=True)
    assert not bg.pending and bg.image is None and bg._count == 0


def test_auto_rejects_moving_dark_and_stale_scenes_and_disabled_mode():
    for case in ("moving", "dark", "stale", "disabled", "invalid"):
        bg = Background()
        for n in range(50):
            frame = np.full((90, 160, 3), 100 if n % 2 == 0 else 140, np.uint8)
            if case == "dark":
                frame[:] = 0
            mask = np.full((90, 160), np.nan if case == "invalid" else 0, np.float32)
            auto_tick(bg, n * 0.1, frame=frame, mask=mask, enabled=case != "disabled", fresh=case != "stale")
        assert bg.image is None and not bg.pending, case


def test_auto_captures_textured_room_under_exposure_flicker_and_sensor_noise():
    rng = np.random.default_rng(42)
    room = rng.integers(40, 190, (90, 160, 1)).astype(np.float32)
    room = np.repeat(room, 3, axis=2)
    bg = Background()
    saved_at = []
    for n in range(50):
        gain = 1 + 0.04 * np.sin(n * 0.8)
        offset = 8 * np.sin(n * 0.7)
        noisy = room * gain + offset + rng.normal(0, 1, room.shape)
        frame = np.clip(noisy, 0, 255).astype(np.uint8)
        if auto_tick(bg, n * 0.1, frame=frame):
            saved_at.append(n)
    assert len(saved_at) == 1 and saved_at[0] < 40
    assert bg.image is not None


def test_auto_rejects_local_motion_even_when_global_light_also_changes():
    bg = Background()
    for n in range(60):
        frame = np.full((90, 160, 3), 100 + n % 5, np.uint8)
        x = 10 if n % 2 else 90
        frame[20:65, x:x + 35] = 210
        auto_tick(bg, n * 0.1, frame=frame)
    assert bg.image is None and not bg.pending


def test_auto_fixed_reference_rejects_slow_cumulative_scene_change():
    bg = Background()
    for n in range(60):
        frame = np.full((90, 160, 3), 100, np.uint8)
        frame[10:80, 20:140] = 100 + min(100, n * 2)
        auto_tick(bg, n * 0.1, frame=frame)
    assert bg.image is None and not bg.pending


def test_auto_cancels_average_when_person_returns_during_light_flicker():
    bg = Background()
    for n in range(25):
        auto_tick(bg, n * 0.1, frame=np.full((90, 160, 3), 100 + n % 5, np.uint8))
    assert bg.pending and bg._count > 0
    auto_tick(bg, 2.5, tracked=True)
    assert bg.image is None and not bg.pending and bg._count == 0


def test_auto_rearm_retains_old_background_until_new_capture_finishes():
    bg = Background()
    for t in np.arange(0, 4, 0.1):
        auto_tick(bg, float(t))
    original = bg.image.copy()
    bg.arm_auto()
    new = np.full_like(original, 170)
    for t in np.arange(5, 6.5, 0.1):
        auto_tick(bg, float(t), frame=new)
    np.testing.assert_array_equal(bg.image, original)
    for t in np.arange(6.5, 9, 0.1):
        auto_tick(bg, float(t), frame=new)
    np.testing.assert_array_equal(bg.image, new)
    assert not bg.auto_armed


def test_auto_stall_cancels_partial_average_instead_of_crediting_missing_time():
    bg = Background()
    for t in np.arange(0, 2.5, 0.1):
        auto_tick(bg, float(t))
    assert bg.pending and bg._count > 0
    auto_tick(bg, 10)
    assert not bg.pending and bg._count == 0 and bg.image is None


def test_background_timer_averaging_rejection_and_recapture():
    bg = Background()
    frame = np.full((90, 160, 3), 100, np.uint8)
    mask = np.zeros((90, 160), np.float32)
    bg.request(0)
    assert not bg.update_capture(frame, mask, 2)
    assert bg.image is None
    for n in range(12):
        done = bg.update_capture(frame + n, mask, 3 + n * 0.04)
    assert done
    np.testing.assert_array_equal(bg.image, frame + 5)
    saved = bg.image.copy()
    bg.request(5)
    assert not bg.update_capture(frame, np.ones_like(mask), 8)
    assert not bg.pending and "không thành công" in bg.status
    np.testing.assert_array_equal(bg.image, saved)
    bg.request(10)
    assert not bg.update_capture(frame, mask, 13, tracked_person=True)
    assert "không thành công" in bg.status


def test_mask_smoothing_is_bounded_and_does_not_leave_long_trails():
    smoother = MaskSmoother()
    ones = np.ones((24, 32), np.float32)
    assert smoother.apply(ones, (160, 90)).min() > 0.99
    result = smoother.apply(ones * 0, (160, 90))
    assert result.max() < 0.01
    assert result.shape == (90, 160) and result.dtype == np.float32


def test_drift_uses_only_visible_background_and_has_hysteresis():
    bg = Background()
    bg.image = np.full((90, 160, 3), 100, np.uint8)
    mask = np.zeros((90, 160), np.float32)
    mask[20:80, 60:100] = 1
    frame = bg.image.copy()
    frame[20:80, 60:100] = 220
    for _ in range(8):
        assert not bg.check_drift(frame, mask)
    for _ in range(8):
        bg.check_drift(frame + 30, mask)
    assert "thay đổi" in bg.warning
    for _ in range(12):
        bg.check_drift(frame, mask)
    assert bg.warning == ""


def test_alpha_blend_feathers_edges():
    frame = np.full((1, 3, 3), 200, np.uint8)
    bg = np.full_like(frame, 100)
    mask = np.array([[0, 0.5, 1]], np.float32)
    np.testing.assert_array_equal(replace_person(frame, bg, mask)[0, :, 0], [200, 150, 100])
