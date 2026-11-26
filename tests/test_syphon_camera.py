"""Syphon transport boundary; this is not evidence of a running OBS."""
import numpy as np
import pytest

from animecam.virtual_camera import SyphonCamera


class Server:
    device = "test-metal-device"

    def __init__(self):
        self.published = []
        self.stopped = False

    def publish_frame_texture(self, texture):
        self.published.append(texture)

    def stop(self):
        self.stopped = True


class Texture:
    def __init__(self, device, width, height):
        self.device = device
        self.size = (width, height)


def build():
    server = Server()
    uploaded = []
    camera = SyphonCamera(
        server_factory=lambda: server,
        texture_factory=lambda device, width, height: Texture(device, width, height),
        upload=lambda data, texture: uploaded.append((data, texture)),
    )
    return camera, server, uploaded


def test_syphon_publishes_bgr_frames_as_rgba_and_stops():
    camera, server, uploaded = build()
    assert camera.start(4, 2, 30) == "AnimeCam FX (Syphon)"
    bgr = np.zeros((2, 4, 3), np.uint8)
    bgr[..., 0], bgr[..., 1], bgr[..., 2] = 10, 20, 30
    camera.send(bgr)
    assert camera.frames_sent == 1
    assert camera.active
    data, texture = uploaded[0]
    assert texture.size == (4, 2) and texture.device == "test-metal-device"
    assert len(data) == 4 * 2 * 4
    # BGR (10, 20, 30) becomes RGBA (30, 20, 10, 255).
    assert tuple(data[:4]) == (30, 20, 10, 255)
    assert server.published == [texture]
    camera.stop()
    assert server.stopped and not camera.active
    camera.stop()


def test_syphon_rejects_wrong_frames_and_missing_start():
    camera, _, _ = build()
    with pytest.raises(RuntimeError, match="chưa được bật"):
        camera.send(np.zeros((2, 4, 3), np.uint8))
    camera.start(4, 2, 30)
    with pytest.raises(ValueError, match="BGR uint8"):
        camera.send(np.zeros((3, 4, 3), np.uint8))
    with pytest.raises(ValueError, match="BGR uint8"):
        camera.send(np.zeros((2, 4, 3), np.float32))
    camera.stop()


def test_syphon_start_failure_is_reported_without_leaving_a_server():
    def unavailable():
        raise RuntimeError("Syphon framework missing")

    camera = SyphonCamera(server_factory=unavailable, texture_factory=None, upload=None)
    with pytest.raises(RuntimeError, match="Syphon"):
        camera.start(4, 2, 30)
    assert not camera.active


def test_syphon_texture_failure_stops_the_started_server():
    server = Server()

    def no_texture(*args):
        raise RuntimeError("Metal texture unavailable")

    camera = SyphonCamera(server_factory=lambda: server, texture_factory=no_texture, upload=None)
    with pytest.raises(RuntimeError, match="Syphon"):
        camera.start(4, 2, 30)
    assert server.stopped and not camera.active
