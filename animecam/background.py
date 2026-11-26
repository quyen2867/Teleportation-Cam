"""Empty-room acquisition and drift warnings. Background stays in RAM only."""
import cv2
import numpy as np


class Background:
    def __init__(self):
        self.image = None
        self._due = None
        self._sum = None
        self._count = 0
        self.status = "Chưa có ảnh nền"
        self._drift_count = 0
        self.warning = ""
        self._auto_armed = True
        self._empty_since = None
        self._auto_previous = None
        self._auto_anchor = None
        self._auto_last = None
        self._capture_kind = None

    @property
    def pending(self):
        return self._due is not None

    @property
    def auto_armed(self):
        return self._auto_armed

    def _reset_empty(self):
        self._empty_since = None
        self._auto_previous = None
        self._auto_anchor = None
        self._auto_last = None

    def arm_auto(self):
        self._auto_armed = True
        self._due, self._sum, self._count = None, None, 0
        self._capture_kind = None
        self._reset_empty()
        self.status = "Rời khung hình, giữ camera cố định."

    def request(self, now, delay=3.0):
        self._due = now + delay
        self._sum, self._count = None, 0
        self._capture_kind = "manual"
        self._reset_empty()
        self.status = "Rời khung hình — sẽ chụp sau 3 giây"

    @staticmethod
    def _auto_empty(mask, tracked_person):
        if tracked_person or not np.isfinite(mask).all():
            return False
        # Strict thresholds for unattended acquisition, unlike manual capture.
        return float(np.mean(mask > 0.12)) < 0.004 and float(np.mean(mask > 0.65)) < 0.0005

    @staticmethod
    def _same_scene(current, reference):
        # Auto exposure changes brightness/contrast across the whole image.
        # Fit only a bounded, global lighting change; spatial motion remains
        # in the residual. The fixed anchor also catches slow camera movement.
        low, high = np.percentile(reference, (10, 90))
        cur_low, cur_high = np.percentile(current, (10, 90))
        gain = (cur_high - cur_low) / (high - low) if high - low > 15 else 1.0
        if not 0.8 <= gain <= 1.25:
            return False
        difference = current - reference * gain
        offset = float(np.median(difference))
        if abs(offset) > 24:
            return False
        residual = np.abs(difference - offset)
        return float(np.mean(residual)) < 2.5 and float(np.mean(residual > 10)) < 0.02

    def update_auto(self, frame, mask, now, tracked_person=False, enabled=True, fresh=True):
        if not enabled:
            self._reset_empty()
            if self._capture_kind == "auto":
                self._due, self._sum, self._count, self._capture_kind = None, None, 0, None
                self.status = "Đã dừng tự chụp nền"
            elif self._auto_armed and self.image is None and self._capture_kind != "manual":
                self.status = "Tự chụp đã tắt. Bấm Chụp nền trống để chụp."
            return
        if not self._auto_armed or self._capture_kind == "manual":
            return
        if not fresh or not self._auto_empty(mask, tracked_person):
            self._reset_empty()
            if self._capture_kind == "auto":
                self._due, self._sum, self._count, self._capture_kind = None, None, 0, None
            self.status = "Chờ mọi người rời khung hình…"
            return
        gray = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
        if float(np.mean(gray)) < 8 or float(np.mean(gray)) > 247:
            self._reset_empty()
            self._due, self._sum, self._count, self._capture_kind = None, None, 0, None
            self.status = "Hình quá tối hoặc quá sáng."
            return
        stable = False
        if self._auto_previous is not None and self._auto_last is not None and 0 < now - self._auto_last <= 0.35:
            stable = self._same_scene(gray, self._auto_previous)
            if stable and self._auto_anchor is not None:
                stable = self._same_scene(gray, self._auto_anchor)
        self._auto_previous, self._auto_last = gray, now
        if not stable:
            self._empty_since = None
            self._auto_anchor = gray.copy()
            if self._capture_kind == "auto":
                self._due, self._sum, self._count, self._capture_kind = None, None, 0, None
            self.status = "Giữ camera cố định…"
            return
        if self._capture_kind == "auto":
            return  # update_capture verifies and averages each fresh frame below
        if self._empty_since is None:
            self._empty_since = now
        elapsed = now - self._empty_since
        if elapsed < 2.0:
            self.status = f"Nền ổn định: {elapsed:.1f}/2,0 giây"
            return
        self._due, self._sum, self._count = now, None, 0
        self._capture_kind = "auto"
        self.status = "Đang tự chụp nền trống…"

    def update_capture(self, frame, mask, now, tracked_person=False):
        if self._due is None:
            return False
        if now < self._due:
            self.status = f"Rời khung hình — còn {self._due - now:.1f} giây"
            return False
        invalid = (not self._auto_empty(mask, tracked_person) if self._capture_kind == "auto"
                   else tracked_person or not np.isfinite(mask).all() or float(np.mean(mask > 0.4)) > 0.025)
        if invalid:
            self._due, self._sum, self._count = None, None, 0
            self._capture_kind = None
            self._reset_empty()
            self.status = "Chụp không thành công: vẫn còn người."
            return False
        if self._sum is None:
            self._sum = np.zeros(frame.shape, dtype=np.float32)
        self._sum += frame
        self._count += 1
        self.status = f"Đang chụp nền trống… {self._count}/12"
        if self._count < 12:
            return False
        self.image = np.clip(self._sum / self._count, 0, 255).astype(np.uint8)
        self._due, self._sum, self._count = None, None, 0
        self._capture_kind = None
        self._auto_armed = False
        self._reset_empty()
        self.warning, self._drift_count = "", 0
        self.status = "Đã chụp nền trống"
        return True

    def check_drift(self, frame, mask):
        if self.image is None:
            return ""
        size = (160, 90)
        live = cv2.cvtColor(cv2.resize(frame, size), cv2.COLOR_BGR2GRAY).astype(np.float32)
        bg = cv2.cvtColor(cv2.resize(self.image, size), cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Exclude the person and a safety band; only compare observable background.
        small_mask = cv2.resize(mask, size)
        safe = cv2.dilate((small_mask > 0.08).astype(np.uint8), np.ones((9, 9), np.uint8)) == 0
        if np.count_nonzero(safe) < safe.size * 0.12:
            return self.warning
        difference = live[safe] - bg[safe]
        illumination = abs(float(np.median(difference)))
        structure = float(np.mean(np.abs(difference - np.median(difference))))
        drift = illumination > 22 or structure > 16
        self._drift_count = min(12, self._drift_count + 1) if drift else max(0, self._drift_count - 1)
        if self._drift_count >= 6:
            self.warning = "Camera, căn phòng hoặc ánh sáng đã thay đổi — hãy chụp lại nền"
        elif self._drift_count == 0:
            self.warning = ""
        return self.warning


def replace_person(frame, background, mask, amount=1.0):
    if frame.shape != background.shape or mask.shape != frame.shape[:2]:
        raise ValueError("Kích thước hình, ảnh nền và vùng tách người phải trùng nhau")
    alpha = np.clip(mask * amount, 0, 1).astype(np.float32)
    # OpenCV's native SIMD blend avoids multiple full-frame float RGB buffers.
    return cv2.blendLinear(frame, background, 1 - alpha, alpha)
