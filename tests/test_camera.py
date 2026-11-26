"""Camera ownership and shared-mode failure behavior; no real device access."""
import threading
import time

import numpy as np
import pytest

import animecam.camera as module
import animecam.shared_camera as shared
from animecam.config import Settings


def test_shared_camera_owns_native_session_on_reader_thread_and_releases_on_stop(monkeypatch):
    if module.os.name != "nt":
        pytest.skip("Windows shared camera")
    calls = []

    class Device:
        def __init__(self, index):
            assert index == 0

        def open(self):
            calls.append(("open", threading.get_ident()))

        def read(self):
            time.sleep(0.002)
            return np.full((120, 160, 3), 100, np.uint8)

        def close(self):
            calls.append(("close", threading.get_ident()))

    monkeypatch.setattr(shared, "SharedCamera", Device)
    camera = module.Camera(Settings(camera_mode="shared"))
    camera.open()
    frame = camera.next_frame(0)
    assert frame is not None and frame[2].shape == (120, 160, 3)
    camera.close()
    assert calls[0][0] == "open" and calls[-1][0] == "close"
    assert calls[0][1] == calls[-1][1] != threading.get_ident()
    assert not camera._thread.is_alive()


def test_shared_failure_does_not_silently_fall_back_to_exclusive_capture(monkeypatch):
    if module.os.name != "nt":
        pytest.skip("Windows shared camera")
    released = []

    class UnsupportedDevice:
        def __init__(self, index):
            pass

        def open(self):
            raise RuntimeError("Driver does not support sharing")

        def close(self):
            released.append(True)

    def exclusive(*args):
        raise AssertionError("Shared mode must never open DirectShow as a silent fallback")

    monkeypatch.setattr(shared, "SharedCamera", UnsupportedDevice)
    monkeypatch.setattr(module.cv2, "VideoCapture", exclusive)
    camera = module.Camera(Settings(camera_mode="shared"))
    with pytest.raises(RuntimeError, match="does not support sharing"):
        camera.open()
    camera.close()
    assert released == [True]
