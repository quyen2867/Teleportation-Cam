"""File-based teleport cue; no generated fallback. Bounded background playback."""
from pathlib import Path
import queue
import threading

import numpy as np

from animecam.config import resource_root


def default_sound_path():
    return resource_root() / "assets" / "goku-instant-transmission.mp3"


def load_sound(path=None):
    import soundfile as sf

    selected = Path(path) if path else default_sound_path()
    if not selected.is_file():
        raise FileNotFoundError("Không tìm thấy tệp âm thanh. Hãy chọn lại tệp hoặc dùng tiếng Goku mặc định.")
    if selected.stat().st_size > 8_000_000:
        raise ValueError("Tệp âm thanh phải nhỏ hơn 8 MB")
    with sf.SoundFile(str(selected)) as audio:
        if audio.channels not in (1, 2) or not 8000 <= audio.samplerate <= 96000:
            raise ValueError("Âm thanh cần có 1–2 kênh và tần số lấy mẫu từ 8 đến 96 kHz")
        if not 0 < audio.frames <= audio.samplerate * 10:
            raise ValueError("Âm thanh phải dài hơn 0 và không quá 10 giây")
        samples = audio.read(dtype="float32", always_2d=True)
        rate = audio.samplerate
    if not len(samples) or not np.isfinite(samples).all():
        raise ValueError("Dữ liệu âm thanh không hợp lệ")
    samples = np.ascontiguousarray(np.clip(samples, -1, 1))
    samples.flags.writeable = False
    return samples, rate


class SoundPlayer:
    def __init__(self, on_error=None, backend=None):
        self.samples = None
        self.sample_rate = None
        self._cached_key = None
        self._backend = backend
        self._on_error = on_error or (lambda message: None)
        self._requests = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._thread = None

    def _get_backend(self):
        if self._backend is None:
            import sounddevice
            self._backend = sounddevice
        return self._backend

    def outputs(self):
        return [(i, d["name"]) for i, d in enumerate(self._get_backend().query_devices())
                if d["max_output_channels"] > 0]

    def play(self, volume=0.3, device=-1, path=""):
        if self._stop.is_set() or volume <= 0:
            return
        if not 0 <= volume <= 1 or device < -1:
            raise ValueError("Âm lượng hoặc thiết bị phát không hợp lệ")
        try:
            self._requests.put_nowait((volume, device, path))
        except queue.Full:
            # A pending cue already exists; do not build up delayed sounds.
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="return-audio", daemon=True)
            self._thread.start()

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    volume, device, path = self._requests.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    selected = Path(path) if path else default_sound_path()
                    stat = selected.stat()
                    key = (str(selected.resolve()), stat.st_mtime_ns, stat.st_size)
                    if key != self._cached_key:
                        self.samples, self.sample_rate = load_sound(selected)
                        self._cached_key = key
                    self._get_backend().play(self.samples * volume, self.sample_rate,
                                             device=None if device == -1 else device, blocking=False)
                except Exception as exc:
                    if not self._stop.is_set():
                        self._on_error(f"Không phát được âm thanh. Kiểm tra thiết bị phát đã chọn. Chi tiết: {exc}")
        finally:
            if self._backend is not None:
                try:
                    self._backend.stop()
                except Exception:
                    pass

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
