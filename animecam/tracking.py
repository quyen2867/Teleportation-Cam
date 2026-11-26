"""MediaPipe Tasks tracking plus independently testable gesture geometry/debounce."""
from dataclasses import dataclass, field
from contextlib import ExitStack
import math

import cv2
import numpy as np


@dataclass
class Observation:
    # None means tracking unknown; 0 means an observed non-gesture.
    score: float | None
    reason: str
    hands: list = field(default_factory=list)
    face: object = None
    forehead: tuple | None = None
    input_size: tuple | None = None


def _points(landmarks, width, height):
    return np.asarray([(p.x * width, p.y * height, p.z * width) for p in landmarks], dtype=np.float32)


def _straight(points, mcp, pip, dip, tip):
    a, b = points[mcp] - points[pip], points[tip] - points[pip]
    cosine = float(np.dot(a, b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-6))
    angle = math.degrees(math.acos(np.clip(cosine, -1, 1)))
    reach = np.linalg.norm(points[tip] - points[0]) / max(np.linalg.norm(points[pip] - points[0]), 1e-6)
    return angle > 148 and reach > 1.10


def gesture_geometry(hands, face, width, height, sensitivity=0.5) -> Observation:
    if face is None or len(face) < 455:
        return Observation(None, "Chưa nhận được khuôn mặt", hands, face)
    f = _points(face, width, height)
    vertical = f[152, :2] - f[10, :2]
    face_height = float(np.linalg.norm(vertical))
    face_width = float(np.linalg.norm(f[454, :2] - f[234, :2]))
    if face_width < 35 or face_height < 45:
        return Observation(None, "Hãy đến gần camera hơn", hands, face)
    down = vertical / face_height
    across = np.array([down[1], -down[0]])
    center = (f[10, :2] + f[151, :2]) * 0.5
    radius_x = face_width * (0.30 + sensitivity * 0.18)
    radius_y = face_height * (0.13 + sensitivity * 0.09)
    forehead = (tuple(center), tuple(across), tuple(down), radius_x, radius_y)
    best, reason = 0.0, "Đưa hai ngón tay lên trán"
    for hand in hands:
        if len(hand) != 21:
            continue
        p = _points(hand, width, height)
        if not (_straight(p, 5, 6, 7, 8) and _straight(p, 9, 10, 11, 12)):
            reason = "Duỗi thẳng ngón trỏ và ngón giữa"
            continue
        if _straight(p, 13, 14, 15, 16) or _straight(p, 17, 18, 19, 20):
            reason = "Gập ngón áp út và ngón út"
            continue
        if np.linalg.norm(p[8, :2] - p[12, :2]) > face_width * 0.34:
            reason = "Đặt hai đầu ngón tay gần nhau"
            continue
        delta = p[[8, 12], :2] - center
        radii = np.sqrt((delta @ across / radius_x) ** 2 + (delta @ down / radius_y) ** 2)
        distance = float(np.max(radii))
        score = float(np.clip(1.4 - distance * 0.65, 0, 1))
        if score > best:
            best = score
            reason = "Giữ nguyên tư thế" if score >= 0.68 else "Đưa đầu ngón tay sát trán hơn"
    return Observation(best, reason, hands, face, forehead, (width, height))


@dataclass
class GestureStatus:
    triggered: bool
    progress: float
    score: float
    label: str


class GestureGate:
    """Time-based hysteresis, occlusion grace, release latch, and cooldown.

    Unknown tracking never rearms a fired gesture. A visible neutral pose is
    required, so holding the pose through an occlusion cannot toggle twice.
    """
    def __init__(self, hold=0.5, cooldown=1.2, grace=0.16, release=0.25):
        self.hold, self.cooldown, self.grace, self.release = hold, cooldown, grace, release
        self.reset()

    def reset(self):
        self._last = None
        self._last_known = None
        self._filtered = 0.0
        self._active = False
        self._held = 0.0
        self._latched = False
        self._released = 0.0
        self._next_allowed = 0.0
        self._previous_known = False

    def require_release(self):
        self._latched = True
        self._held = self._released = 0.0

    def update(self, score: float | None, now: float) -> GestureStatus:
        dt = 0.0 if self._last is None else max(0.0, now - self._last)
        self._last = now
        if score is None:
            self._released = 0.0
            self._previous_known = False
            if self._last_known is None or now - self._last_known > self.grace:
                self._active, self._held, self._filtered = False, 0.0, 0.0
            return GestureStatus(False, self._held / self.hold, self._filtered, "Tạm mất nhận diện")
        # Do not credit unobserved time or a stalled pipeline toward a hold/release.
        credit = min(dt, 0.10) if self._previous_known and dt <= self.grace else 0.0
        if dt > self.grace:
            self._held = self._released = 0.0
        self._previous_known = True
        self._last_known = now
        alpha = 1 - math.exp(-min(dt, 0.2) / 0.07) if dt else 1.0
        self._filtered += alpha * (score - self._filtered)
        if self._latched:
            self._released = self._released + credit if score < 0.35 else 0.0
            if self._released >= self.release:
                self._latched, self._held, self._active = False, 0.0, False
            return GestureStatus(False, 0.0, self._filtered, "Hạ tay trước khi thực hiện lại")
        if now < self._next_allowed:
            return GestureStatus(False, 0.0, self._filtered, "Chờ trước lần tiếp theo")
        self._active = self._filtered >= (0.48 if self._active else 0.68)
        self._held = self._held + credit if self._active and score >= 0.48 else 0.0
        if self._held >= self.hold:
            self._latched = True
            self._released = self._held = 0.0
            self._next_allowed = now + self.cooldown
            return GestureStatus(True, 1.0, self._filtered, "Đã nhận cử chỉ")
        return GestureStatus(False, min(self._held / self.hold, 1), self._filtered,
                             "Giữ tay ổn định" if self._active else "Sẵn sàng")


class Tracker:
    def __init__(self, paths):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self.mp = mp
        self._stack = ExitStack()
        try:
            self.hands = self._stack.enter_context(vision.HandLandmarker.create_from_options(
                vision.HandLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=str(paths["hand_landmarker.task"])),
                    running_mode=vision.RunningMode.VIDEO, num_hands=2,
                    min_hand_detection_confidence=0.55, min_tracking_confidence=0.55,
                )))
            self.face = self._stack.enter_context(vision.FaceLandmarker.create_from_options(
                vision.FaceLandmarkerOptions(
                    base_options=python.BaseOptions(model_asset_path=str(paths["face_landmarker.task"])),
                    running_mode=vision.RunningMode.VIDEO, num_faces=1,
                    output_face_blendshapes=False, output_facial_transformation_matrixes=False,
                )))
        except Exception:
            self._stack.close()
            raise

    def process(self, rgb, timestamp_ms, sensitivity):
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        hands = self.hands.detect_for_video(image, timestamp_ms).hand_landmarks
        faces = self.face.detect_for_video(image, timestamp_ms).face_landmarks
        return gesture_geometry(hands, faces[0] if faces else None, rgb.shape[1], rgb.shape[0], sensitivity)

    def close(self):
        self._stack.close()


def draw_debug(frame, observation):
    h, w = frame.shape[:2]
    for hand in observation.hands:
        pts = [(int(p.x * w), int(p.y * h)) for p in hand]
        for chain in ((0, 1, 2, 3, 4), (0, 5, 6, 7, 8), (5, 9, 10, 11, 12),
                      (9, 13, 14, 15, 16), (13, 17, 18, 19, 20), (0, 17)):
            for a, b in zip(chain, chain[1:]):
                cv2.line(frame, pts[a], pts[b], (100, 220, 140), 1, cv2.LINE_AA)
        for point in pts:
            cv2.circle(frame, point, 3, (100, 240, 255), -1, cv2.LINE_AA)
    if observation.forehead and observation.input_size:
        center, across, down, rx, ry = observation.forehead
        sx, sy = w / observation.input_size[0], h / observation.input_size[1]
        points = []
        for theta in np.linspace(0, math.tau, 60):
            p = np.array(center) + np.array(across) * rx * math.cos(theta) + np.array(down) * ry * math.sin(theta)
            points.append((int(p[0] * sx), int(p[1] * sy)))
        cv2.polylines(frame, [np.asarray(points, dtype=np.int32)], True, (255, 170, 80), 2, cv2.LINE_AA)
