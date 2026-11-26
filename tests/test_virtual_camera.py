import numpy as np
import pytest

from animecam.virtual_camera import VirtualCamera


class Backend:
    """Test transport boundary; this is not evidence of an installed OBS driver."""
    device = "Test backend"

    def __init__(self, **options):
        self.options = options
        self.received = []
        self.closed = False

    def send(self, frame):
        self.received.append(frame.copy())

    def close(self):
        self.closed = True


def test_sends_actual_bgr_composited_pixels_and_closes():
    from animecam.effects import InstantTransmission
    from animecam.config import Settings

    output = VirtualCamera(factory=Backend)
    output.start(160, 90, 30)
    backend = output._camera
    live = np.full((90, 160, 3), 230, np.uint8)
    bg = np.full_like(live, (10, 40, 70))
    mask = np.ones((90, 160), np.float32)
    effect = InstantTransmission()
    effect.trigger(0, True)
    hidden = effect.render(live, mask, bg, 1, Settings())
    output.send(hidden)
    assert output.frames_sent == 1
    np.testing.assert_array_equal(backend.received[0], bg)
    assert backend.options["fmt"].name == "BGR"
    output.stop()
    assert backend.closed and not output.active
    output.stop()


def test_backend_failure_and_wrong_frame_are_reported():
    def unavailable(**kwargs):
        raise RuntimeError("Driver missing")
    output = VirtualCamera(factory=unavailable)
    with pytest.raises(RuntimeError, match="cài OBS Studio"):
        output.start(160, 90, 30)
    assert not output.active
    output = VirtualCamera(factory=Backend)
    output.start(160, 90, 30)
    with pytest.raises(ValueError, match="BGR uint8"):
        output.send(np.zeros((20, 30, 3), np.uint8))
    output.stop()
