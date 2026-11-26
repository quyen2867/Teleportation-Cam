"""QThread pipeline; UI polls a single packet and never queues video signals."""
from dataclasses import dataclass, replace
from collections.abc import Callable
import logging
import queue
import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from animecam.background import Background
from animecam.camera import Camera
from animecam.config import Settings
from animecam.effects import InstantTransmission
from animecam.effects.base import Effect
from animecam.models import model_paths
from animecam.segmentation import Segmenter
from animecam.tracking import GestureGate, Tracker, draw_debug
from animecam.virtual_camera import VirtualCamera

log = logging.getLogger(__name__)


@dataclass
class Packet:
    frame: np.ndarray
    output: np.ndarray
    fps: float
    inference_ms: float
    latency_ms: float
    state: str
    gesture: str
    progress: float
    score: float
    background: str
    background_ready: bool
    warning: str
    virtual: bool
    frames_sent: int


class Pipeline(QThread):
    error = Signal(str)
    notice = Signal(str)
    virtual_status = Signal(bool, str)
    return_sound = Signal()

    def __init__(self, settings: Settings, parent=None, effect_factory: Callable[[], Effect] = InstantTransmission):
        super().__init__(parent)
        self._settings = settings
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._commands = queue.Queue(maxsize=16)
        self._packet = None
        self._effect_factory = effect_factory

    def configure(self, **changes):
        with self._lock:
            self._settings = replace(self._settings, **changes)

    def command(self, name):
        try:
            self._commands.put_nowait(name)
        except queue.Full:
            self.notice.emit("Có nhiều thao tác đang chờ; vui lòng đợi xử lý")

    def stop(self):
        self._stop.set()

    def take_packet(self):
        with self._lock:
            packet, self._packet = self._packet, None
        return packet

    def _trigger_effect(self, effect, now, ready, settings):
        returning = effect.state.value == "HIDDEN"
        accepted = effect.trigger(now, ready, quick_exit=settings.quick_disappear)
        if accepted and returning and settings.sound_enabled:
            self.return_sound.emit()
        return accepted

    def run(self):
        camera = tracker = segmenter = None
        virtual = VirtualCamera()
        try:
            with self._lock:
                settings = self._settings
            cv2.setNumThreads(2)
            self.notice.emit("Đang chuẩn bị camera…")
            paths = model_paths()
            tracker = Tracker(paths)
            segmenter = Segmenter(paths["selfie_segmenter.tflite"])
            if self._stop.is_set():
                return
            camera = Camera(settings)
            camera.open()
            self.notice.emit("Webcam đã bật. Rời khung hình để tự chụp nền trống." if settings.auto_background
                             else "Webcam đã bật. Hãy chụp nền trống để bật dịch chuyển.")
            background, effect, gate = Background(), self._effect_factory(), GestureGate()
            sequence, index, timestamp = 0, 0, -1
            mask = None
            fps, previous_finish = 0.0, None
            start = time.monotonic()
            last_frame = start
            output_size = None
            source_size = None
            background_reset_pending = False
            previous_enabled = settings.enabled
            observation = None
            while not self._stop.is_set():
                item = camera.next_frame(sequence)
                if item is None:
                    if time.monotonic() - last_frame > 6:
                        raise RuntimeError("Không nhận được hình webcam trong 6 giây")
                    continue
                sequence, captured, frame = item
                last_frame = time.monotonic()
                with self._lock:
                    settings = self._settings
                h, w = frame.shape[:2]
                if output_size is None:
                    output_size = (w, h)
                    source_size = (w, h)
                    self.notice.emit("Camera đang bật")
                elif source_size != (w, h):
                    if settings.camera_mode != "shared":
                        raise RuntimeError("Webcam đã đổi độ phân giải. Hãy bật lại camera và chụp lại nền.")
                    # A controlling app may change the physical camera format.
                    # Keep the virtual stream dimensions stable and invalidate
                    # acquisition geometry. Never reveal the live feed if hidden.
                    source_size = (w, h)
                    background_reset_pending = True
                    mask, observation = None, None
                    gate.require_release()
                    self.notice.emit("Camera đã đổi định dạng; cần chụp lại nền.")
                if (w, h) != output_size:
                    frame = cv2.resize(frame, output_size)
                    w, h = output_size
                if background_reset_pending and effect.state.value == "VISIBLE":
                    background = Background()
                    background_reset_pending = False
                elif background_reset_pending:
                    background.warning = "Camera đổi định dạng. Chụp lại nền sau khi hiện lại."
                now = time.monotonic()
                processing_started = now
                timestamp = max(timestamp + 1, int((now - start) * 1000))
                small_w = min(w, settings.inference_width)
                small_h = max(1, round(h * small_w / w))
                rgb = cv2.cvtColor(cv2.resize(frame, (small_w, small_h)), cv2.COLOR_BGR2RGB)
                ai_started = time.monotonic()
                if effect.state.value in ("DISAPPEARING", "APPEARING") and observation is not None:
                    # Gestures cannot toggle mid-transition. Keep segmentation
                    # live, but spend this short interval on VFX instead of hands.
                    observation = replace(observation, score=None, reason="Nhận diện sẽ tiếp tục sau hiệu ứng")
                else:
                    observation = tracker.process(rgb, timestamp, settings.sensitivity)
                # New masks every frame by default. Economy mode is explicit.
                mask_fresh = mask is None or index % settings.segmentation_every == 0 or (settings.auto_background and background.auto_armed)
                if mask_fresh:
                    seg_rgb = cv2.resize(rgb, (256, 144))
                    mask = segmenter.process(seg_rgb, timestamp, (w, h))
                inference_ms = (time.monotonic() - ai_started) * 1000
                now = time.monotonic()
                if previous_enabled != settings.enabled:
                    effect.restore()
                    gate.reset()
                    previous_enabled = settings.enabled
                status = gate.update(observation.score, now)
                background.update_auto(
                    frame, mask, now, bool(observation.hands) or observation.face is not None,
                    enabled=settings.auto_background and effect.state.value not in ("DISAPPEARING", "APPEARING"),
                    fresh=mask_fresh,
                )
                captured_background = background.update_capture(
                    frame, mask, now, bool(observation.hands) or observation.face is not None
                )
                if captured_background:
                    effect.restore()
                    gate.reset()
                    self.notice.emit("Đã chụp nền trống")
                suppress_gesture = False
                while True:
                    try:
                        command = self._commands.get_nowait()
                    except queue.Empty:
                        break
                    if command == "capture":
                        suppress_gesture = True
                        effect.restore()
                        gate.reset()
                        background.request(now)
                    elif command == "auto_capture":
                        suppress_gesture = True
                        background.arm_auto()
                        self.configure(auto_background=True)
                    elif command == "restore":
                        suppress_gesture = True
                        effect.restore()
                        # Manual recovery still requires a neutral pose before rearm.
                        gate.require_release()
                    elif command == "trigger":
                        suppress_gesture = True
                        if not settings.enabled:
                            self.notice.emit("Hãy bật hiệu ứng dịch chuyển trước")
                        elif self._trigger_effect(effect, now, background.image is not None and not background.pending, settings):
                            gate.require_release()
                        else:
                            self.notice.emit("Hãy chụp nền trống trước hoặc chờ hiệu ứng kết thúc")
                    elif command == "hide":
                        suppress_gesture = True
                        if effect.hide(background.image is not None and not background.pending):
                            settings = replace(settings, enabled=True, complete_hide=True)
                            self.configure(enabled=True, complete_hide=True)
                            previous_enabled = True
                            gate.require_release()
                            self.notice.emit("Đã ẩn · F8 để hiện ngay")
                        else:
                            self.notice.emit("Hãy chụp nền trống trước khi ẩn")
                    elif command == "virtual_start":
                        try:
                            device = virtual.start(w, h, settings.fps)
                            self.virtual_status.emit(True, f"Đã kết nối {device}; đang chờ hình đầu tiên")
                        except Exception as exc:
                            self.error.emit(str(exc))
                            self.virtual_status.emit(False, "Chưa dùng được camera ảo")
                    elif command == "virtual_stop":
                        virtual.stop()
                        self.virtual_status.emit(False, "Camera ảo đã dừng")
                if status.triggered and not suppress_gesture and settings.enabled and not background.pending:
                    if not self._trigger_effect(effect, now, background.image is not None, settings):
                        if background.image is None:
                            self.notice.emit("Đã nhận cử chỉ; hãy chụp nền trống để dịch chuyển")
                if index % 10 == 0 and not background_reset_pending:
                    background.check_drift(frame, mask)
                output = effect.render(frame, mask, background.image, now, settings)
                if settings.mirror:
                    output = cv2.flip(output, 1)
                if virtual.active:
                    try:
                        virtual.send(output)
                    except Exception as exc:
                        virtual.stop()
                        self.virtual_status.emit(False, "Đã dừng camera ảo do lỗi truyền hình")
                        self.error.emit(f"Không gửi được hình tới camera ảo. Chi tiết: {exc}")
                # Debug overlays are preview-only, never sent to the virtual camera.
                preview = output.copy()
                if settings.debug and effect.state.value == "VISIBLE":
                    overlay = frame.copy()
                    draw_debug(overlay, observation)
                    if settings.mirror:
                        overlay = cv2.flip(overlay, 1)
                    # Hide the entire raw inset during effects: OBS users may
                    # capture this preview instead of the dedicated clean window.
                    ph, pw = max(1, h // 3), max(1, w // 3)
                    preview[:ph, :pw] = cv2.resize(overlay, (pw, ph))
                finished = time.monotonic()
                if previous_finish is not None:
                    measured = 1 / max(finished - previous_finish, 1e-6)
                    fps = measured if fps == 0 else 0.90 * fps + 0.10 * measured
                previous_finish = finished
                packet = Packet(
                    preview, output, fps, inference_ms, (finished - captured) * 1000,
                    effect.state.value, f"{status.label} • {observation.reason}",
                    status.progress, status.score, background.status, background.image is not None,
                    background.warning, virtual.active, virtual.frames_sent,
                )
                with self._lock:
                    self._packet = packet
                index += 1
                self._stop.wait(max(0, 1 / settings.fps - (time.monotonic() - processing_started)))
        except Exception as exc:
            log.exception("Pipeline stopped")
            self.error.emit(str(exc))
        finally:
            for resource in (virtual, camera, tracker, segmenter):
                if resource is not None:
                    try:
                        resource.stop() if resource is virtual else resource.close()
                    except Exception as exc:
                        log.exception("Resource cleanup failed")
                        self.error.emit(str(exc))
            self.virtual_status.emit(False, "Camera ảo đã dừng")
