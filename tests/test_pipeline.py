"""Pipeline orchestration tests with explicit test doubles, no device claims."""
import time

import numpy as np

from animecam.config import Settings
import animecam.pipeline as module
from animecam.tracking import Observation


def install_resources(monkeypatch, fail=False, stop_after=1):
    closed, delivered = [], []
    holder = {}

    class Camera:
        def __init__(self, settings):
            pass

        def open(self):
            pass

        def next_frame(self, after):
            if fail:
                raise RuntimeError("Test camera disconnected")
            return 1, time.monotonic(), np.full((120, 160, 3), (10, 30, 60), np.uint8)

        def close(self):
            closed.append("camera")

    class Tracker:
        def __init__(self, paths):
            pass

        def process(self, *args):
            return Observation(None, "Test blank scene")

        def close(self):
            closed.append("tracker")

    class Segmenter:
        def __init__(self, path):
            pass

        def process(self, rgb, timestamp, size):
            holder["segmentation_calls"] = holder.get("segmentation_calls", 0) + 1
            return np.zeros((size[1], size[0]), np.float32)

        def close(self):
            closed.append("segmenter")

    class Virtual:
        active = False
        frames_sent = 0

        def start(self, *args):
            self.active = True
            return "Test transport"

        def send(self, frame):
            delivered.append(frame.copy())
            self.frames_sent += 1
            if self.frames_sent >= stop_after:
                holder["worker"].stop()

        def stop(self):
            self.active = False
            closed.append("virtual")

    monkeypatch.setattr(module, "model_paths", lambda: {"selfie_segmenter.tflite": "test"})
    for name, cls in (("Camera", Camera), ("Tracker", Tracker), ("Segmenter", Segmenter), ("VirtualCamera", Virtual)):
        monkeypatch.setattr(module, name, cls)
    return closed, delivered, holder


def test_pipeline_sends_processed_frame_publishes_packet_and_releases_every_resource(monkeypatch):
    closed, delivered, holder = install_resources(monkeypatch)
    worker = module.Pipeline(Settings(width=160, height=120, enabled=False, mirror=True))
    holder["worker"] = worker
    worker.command("virtual_start")
    worker.run()
    assert len(delivered) == 1
    np.testing.assert_array_equal(delivered[0][0, 0], [10, 30, 60])
    packet = worker.take_packet()
    assert packet.frames_sent == 1 and packet.virtual
    assert packet.inference_ms >= 0 and packet.latency_ms >= 0
    np.testing.assert_array_equal(packet.output, delivered[0])
    assert worker.take_packet() is None
    assert set(closed) == {"virtual", "camera", "tracker", "segmenter"}


def test_pipeline_handles_disconnect_and_closes_resources(monkeypatch):
    closed, _, holder = install_resources(monkeypatch, fail=True)
    worker = module.Pipeline(Settings())
    holder["worker"] = worker
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert errors and "disconnected" in errors[0]
    assert set(closed) == {"virtual", "camera", "tracker", "segmenter"}


def test_hide_now_sends_only_background_and_never_adds_raw_debug_inset(monkeypatch):
    closed, delivered, holder = install_resources(monkeypatch)
    bg = np.full((120, 160, 3), (80, 90, 100), np.uint8)
    original_background = module.Background

    class CapturedBackground(original_background):
        def __init__(self):
            super().__init__()
            self.image = bg.copy()

    monkeypatch.setattr(module, "Background", CapturedBackground)
    worker = module.Pipeline(Settings(width=160, height=120, enabled=False, complete_hide=False, debug=True))
    holder["worker"] = worker
    worker.command("virtual_start")
    worker.command("hide")
    worker.run()
    packet = worker.take_packet()
    assert packet.state == "HIDDEN" and packet.virtual
    np.testing.assert_array_equal(delivered[0], bg)
    np.testing.assert_array_equal(packet.output, bg)
    np.testing.assert_array_equal(packet.frame, bg)
    assert set(closed) == {"virtual", "camera", "tracker", "segmenter"}


def test_effect_sound_is_emitted_once_per_accepted_transition():
    from animecam.effects import InstantTransmission

    worker = module.Pipeline(Settings())
    emitted = []
    worker.effect_sound.connect(lambda: emitted.append("cue"))
    effect = InstantTransmission()
    settings = Settings()
    assert not worker._trigger_effect(effect, 0, False, settings)
    assert worker._trigger_effect(effect, 1, True, settings)  # quick disappearance
    assert emitted == ["cue"] and effect.state.value == "HIDDEN"
    assert worker._trigger_effect(effect, 2, True, settings)  # animated return
    assert emitted == ["cue", "cue"] and effect.state.value == "APPEARING"
    assert not worker._trigger_effect(effect, 2.1, True, settings)
    assert emitted == ["cue", "cue"]
    effect.advance(3, 0.5, settings.appear_seconds)
    assert worker._trigger_effect(effect, 4, True, settings)
    assert worker._trigger_effect(effect, 5, True, Settings(sound_enabled=False))
    assert emitted == ["cue", "cue", "cue"]


def test_auto_background_wait_forces_fresh_segmentation_even_in_economy_mode(monkeypatch):
    _, delivered, holder = install_resources(monkeypatch, stop_after=3)
    worker = module.Pipeline(Settings(width=160, height=120, segmentation_every=3, auto_background=True))
    holder["worker"] = worker
    worker.command("virtual_start")
    worker.run()
    assert len(delivered) == 3
    assert holder["segmentation_calls"] == 3


def test_shared_format_change_keeps_output_size_and_never_reveals_hidden_person(monkeypatch):
    _, delivered, holder = install_resources(monkeypatch, stop_after=2)
    saved = np.full((120, 160, 3), (70, 80, 90), np.uint8)
    original_background = module.Background

    class SavedBackground(original_background):
        def __init__(self):
            super().__init__()
            self.image = saved.copy()
            self._auto_armed = False

    def changing_frame(self, after):
        size = (120, 160, 3) if after == 0 else (240, 320, 3)
        return after + 1, time.monotonic(), np.full(size, 220, np.uint8)

    monkeypatch.setattr(module.Camera, "next_frame", changing_frame)
    monkeypatch.setattr(module, "Background", SavedBackground)
    worker = module.Pipeline(Settings(width=160, height=120, camera_mode="shared", debug=True))
    holder["worker"] = worker
    worker.command("virtual_start")
    worker.command("hide")
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert not errors and len(delivered) == 2
    for frame in delivered:
        np.testing.assert_array_equal(frame, saved)
    packet = worker.take_packet()
    assert packet.state == "HIDDEN" and "đổi định dạng" in packet.warning


def test_shared_format_change_invalidates_visible_background_before_next_hide(monkeypatch):
    _, delivered, holder = install_resources(monkeypatch, stop_after=2)

    def changing_frame(self, after):
        size = (120, 160, 3) if after == 0 else (180, 320, 3)
        return after + 1, time.monotonic(), np.full(size, 100, np.uint8)

    monkeypatch.setattr(module.Camera, "next_frame", changing_frame)
    worker = module.Pipeline(Settings(width=160, height=120, camera_mode="shared"))
    holder["worker"] = worker
    worker.command("virtual_start")
    errors = []
    worker.error.connect(errors.append)
    worker.run()
    assert not errors and len(delivered) == 2
    assert all(frame.shape == (120, 160, 3) for frame in delivered)
    assert not worker.take_packet().background_ready
