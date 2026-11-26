import numpy as np
import pytest

from animecam.config import Settings
from animecam.effects import InstantTransmission, State


def scene():
    background = np.full((120, 200, 3), (20, 40, 60), dtype=np.uint8)
    live = background.copy()
    live[20:110, 70:130] = (200, 170, 100)
    mask = np.zeros((120, 200), dtype=np.float32)
    mask[20:110, 70:130] = 1
    return live, background, mask


def test_full_state_cycle_and_manual_restore():
    effect = InstantTransmission()
    assert not effect.trigger(0, False)
    assert effect.state == State.VISIBLE
    assert effect.trigger(1, True)
    assert not effect.trigger(1.1, True)
    effect.advance(1.5, 0.5, 0.5)
    assert effect.state == State.HIDDEN
    assert effect.trigger(3, True)
    assert effect.state == State.APPEARING
    effect.advance(3.5, 0.5, 0.5)
    assert effect.state == State.VISIBLE
    effect.trigger(5, True)
    effect.restore()
    assert effect.state == State.VISIBLE


def test_quick_exit_is_immediate_but_return_has_a_real_short_transition():
    live, bg, mask = scene()
    mask[:] = 0  # returning should not depend on segmentation being perfect
    effect = InstantTransmission()
    assert effect.trigger(0, True, quick_exit=True)
    assert effect.state == State.HIDDEN
    settings = Settings(glow=0, complete_hide=False)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 0, settings), bg)
    assert effect.trigger(1, True, quick_exit=True)
    assert effect.state == State.APPEARING
    np.testing.assert_array_equal(effect.render(live, mask, bg, 1, settings), bg)
    middle = effect.render(live, mask, bg, 1 + settings.appear_seconds / 2, settings)
    assert effect.state == State.APPEARING
    assert not np.array_equal(middle, live) and not np.array_equal(middle, bg)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 1.4, settings), live)
    assert effect.state == State.VISIBLE


def test_hidden_removes_only_mask_and_preserves_live_objects():
    live, bg, mask = scene()
    live[:10, :10] = (0, 250, 0)  # new object outside the person
    effect = InstantTransmission()
    effect.trigger(0, True)
    result = effect.render(live, mask, bg, 1, Settings(complete_hide=False))
    np.testing.assert_array_equal(result[20:110, 70:130], bg[20:110, 70:130])
    np.testing.assert_array_equal(result[:10, :10], live[:10, :10])
    effect.trigger(2, True)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 3, Settings()), live)


@pytest.mark.parametrize("time", [0, 0.1, 0.25, 0.49, 0.5, 0.75])
def test_procedural_vfx_shape_range_and_input_ownership(time):
    live, bg, mask = scene()
    original = live.copy()
    effect = InstantTransmission()
    effect.trigger(0, True)
    result = effect.render(live, mask, bg, time, Settings())
    assert result.shape == live.shape and result.dtype == np.uint8
    np.testing.assert_array_equal(live, original)


def test_disable_or_missing_background_restores_visible():
    live, bg, mask = scene()
    effect = InstantTransmission()
    effect.trigger(0, True)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 0.2, Settings(enabled=False)), live)
    assert effect.state == State.VISIBLE
    effect.trigger(2, True)
    np.testing.assert_array_equal(effect.render(live, mask, None, 3, Settings()), live)
    assert effect.state == State.VISIBLE


@pytest.mark.parametrize("glow", [0.0, 0.8])
def test_720p_transition_uses_bounded_canvas_and_restores_output_size(glow):
    live = np.full((720, 1280, 3), 160, np.uint8)
    background = np.full_like(live, 40)
    mask = np.zeros((720, 1280), np.float32)
    mask[100:700, 400:800] = 1
    effect = InstantTransmission()
    effect.trigger(0, True)
    output = effect.render(live, mask, background, 0.25, Settings(glow=glow))
    assert output.shape == live.shape and output.dtype == np.uint8
    assert effect.state == State.DISAPPEARING


@pytest.mark.parametrize("mask_value", [0.0, 0.15, 0.5, 1.0, float("nan")])
def test_complete_hidden_contains_only_background_even_when_mask_fails(mask_value):
    rng = np.random.default_rng(25)
    bg = rng.integers(0, 256, (120, 200, 3), dtype=np.uint8)
    effect = InstantTransmission()
    effect.trigger(0, True)
    mask = np.full((120, 200), mask_value, np.float32)
    for now in (1, 2, 3):
        # The person and objects can move anywhere, including outside the mask.
        live = rng.integers(0, 256, bg.shape, dtype=np.uint8)
        output = effect.render(live, mask, bg, now, Settings())
        np.testing.assert_array_equal(output, bg)
        assert not np.shares_memory(output, bg)


def test_hide_now_requires_background_and_overrides_approximate_mode_until_return():
    live, bg, mask = scene()
    mask[:] = 0  # segmentation completely missed the person
    effect = InstantTransmission()
    assert not effect.hide(False) and effect.state == State.VISIBLE
    assert effect.hide(True) and effect.state == State.HIDDEN
    settings = Settings(complete_hide=False)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 0, settings), bg)
    assert effect.trigger(1, True)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 2, settings), live)
    # Returning clears the override; a later masked-mode gesture uses live pixels.
    assert effect.trigger(3, True)
    np.testing.assert_array_equal(effect.render(live, mask, bg, 4, settings), live)


@pytest.mark.parametrize("now", [0.11, 0.23, 0.37])
def test_warped_foreground_has_no_black_interpolation_fringe(now):
    white = np.full((125, 203, 3), 255, np.uint8)
    mask = np.ones((125, 203), np.float32)
    effect = InstantTransmission()
    effect.trigger(0, True)
    # White foreground over white background must remain white even at the
    # fractional boundary of a shrinking/translating foreground image.
    result = effect.render(white, mask, white, now, Settings(glow=0))
    assert result.min() >= 254
