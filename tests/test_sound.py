import threading

import numpy as np
import pytest

from animecam.sound import SoundPlayer, load_sound, default_sound_path


def test_bundled_cue_is_the_downloaded_goku_recording_not_a_generated_fallback():
    import hashlib

    samples, rate = load_sound()
    assert samples.dtype == np.float32 and samples.ndim == 2
    assert rate == 44100 and samples.shape[1] == 2
    assert 0.8 < len(samples) / rate < 1.0
    assert np.isfinite(samples).all()
    assert 0.7 < np.max(np.abs(samples)) < 0.9
    assert hashlib.sha256(default_sound_path().read_bytes()).hexdigest() == "358d0e550804650e624356514ccbd0f151b45827f097b1d948db5bba3c35fcdc"


def test_missing_audio_never_generates_another_sound():
    missing = default_sound_path().with_name("missing-sound-test-fixture.mp3")
    assert not missing.exists()
    with pytest.raises(FileNotFoundError, match="Không tìm thấy"):
        load_sound(missing)


def test_sound_uses_requested_volume_device_and_nonblocking_backend_off_ui_thread():
    called = threading.Event()
    caller = threading.get_ident()

    class Backend:
        def query_devices(self):
            return [{"name": "Mic", "max_output_channels": 0},
                    {"name": "Speaker", "max_output_channels": 2}]

        def play(self, data, rate, **kwargs):
            self.data, self.rate, self.options = data, rate, kwargs
            self.thread_id = threading.get_ident()
            called.set()

        def stop(self):
            self.stopped = True

    backend = Backend()
    sound = SoundPlayer(backend=backend)
    assert sound.outputs() == [(1, "Speaker")]
    sound.play(0.2, device=1)
    assert called.wait(2)
    sound.close()
    np.testing.assert_allclose(backend.data, load_sound()[0] * 0.2)
    assert backend.rate == 44100 and backend.options == {"device": 1, "blocking": False}
    assert backend.thread_id != caller and backend.stopped
    assert not sound._thread.is_alive()


def test_audio_device_error_is_reported_and_does_not_raise_into_video_pipeline():
    failed = threading.Event()
    messages = []

    class Backend:
        def play(self, *args, **kwargs):
            raise RuntimeError("Test: no output device")

        def stop(self):
            pass

    def on_error(message):
        messages.append(message)
        failed.set()

    sound = SoundPlayer(on_error=on_error, backend=Backend())
    sound.play()
    assert failed.wait(2)
    sound.close()
    assert "Không phát được âm thanh" in messages[0]
    # Muted and closed players never start/restart a native audio stream.
    muted = SoundPlayer(backend=Backend())
    muted.play(0)
    assert muted._thread is None
    muted.close()
    muted.play()
    assert muted._thread is None
