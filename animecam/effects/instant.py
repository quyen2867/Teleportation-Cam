from enum import Enum
import math

import cv2
import numpy as np

from animecam.background import replace_person
from animecam.config import Settings


class State(str, Enum):
    VISIBLE = "VISIBLE"
    DISAPPEARING = "DISAPPEARING"
    HIDDEN = "HIDDEN"
    APPEARING = "APPEARING"


class InstantTransmission:
    def __init__(self):
        self.state = State.VISIBLE
        self.started = 0.0
        self._force_complete = False
        # Fixed seeds are reused, not appended to an ever-growing particle list.
        self._particles = np.random.default_rng(42).random((54, 4))

    def restore(self):
        self.state = State.VISIBLE
        self._force_complete = False

    def hide(self, background_ready):
        if not background_ready:
            return False
        self.state = State.HIDDEN
        self._force_complete = True
        return True

    def trigger(self, now, background_ready, quick_exit=False):
        if not background_ready:
            return False
        if self.state == State.VISIBLE:
            if quick_exit:
                return self.hide(True)
            self.state = State.DISAPPEARING
        elif self.state == State.HIDDEN:
            self.state = State.APPEARING
        else:
            return False
        self.started = now
        return True

    def advance(self, now, disappear_seconds, appear_seconds):
        if self.state not in (State.DISAPPEARING, State.APPEARING):
            return 0.0
        duration = disappear_seconds if self.state == State.DISAPPEARING else appear_seconds
        progress = min(1.0, max(0.0, (now - self.started) / duration))
        if progress >= 1:
            self.state = State.HIDDEN if self.state == State.DISAPPEARING else State.VISIBLE
        return progress

    def render(self, frame, mask, background, now, settings: Settings):
        if not settings.enabled or background is None:
            self.restore()
            return frame.copy()
        phase = self.state
        p = self.advance(now, settings.disappear_seconds, settings.appear_seconds)
        if self.state == State.VISIBLE:
            self._force_complete = False
            return frame.copy()
        complete = settings.complete_hide or self._force_complete
        if self.state == State.HIDDEN:
            # Do not sample a single live pixel: failed/soft/stale masks must not
            # reveal the person in complete-hide mode. Tracking still sees raw input.
            return background.copy() if complete else replace_person(frame, background, mask)
        output_size = (frame.shape[1], frame.shape[0])
        # The short transition intentionally has motion blur. Render the entire
        # VFX composite on a bounded canvas, then scale once, preserving CPU time.
        if frame.shape[1] > 480:
            size = (480, max(1, round(frame.shape[0] * 480 / frame.shape[1])))
            frame = cv2.resize(frame, size)
            background = cv2.resize(background, size)
            mask = cv2.resize(mask, size)
        cleaned = background.copy() if complete else replace_person(frame, background, mask)
        h, w = frame.shape[:2]
        moments = cv2.moments(mask)
        cx = moments["m10"] / moments["m00"] if moments["m00"] > 1 else w / 2
        cy = moments["m01"] / moments["m00"] if moments["m00"] > 1 else h / 2
        eased = p * p * (3 - 2 * p)
        visibility = 1 - eased if phase == State.DISAPPEARING else eased
        contraction = 1 - visibility if phase == State.DISAPPEARING else 0.0
        sx, sy = 1 - 0.65 * contraction, 1 - 0.12 * contraction
        shift = w * 0.13 * contraction * (1 if phase == State.DISAPPEARING else -1)
        transform = np.array([[sx, 0, cx * (1 - sx) + shift],
                              [0, sy, cy * (1 - sy)]], dtype=np.float32)
        # Warp premultiplied foreground. Warping straight RGB against a black
        # border and applying alpha afterward creates dark interpolation fringes.
        foreground = frame.astype(np.float32) * mask[..., None]
        warped = cv2.warpAffine(foreground, transform, (w, h), flags=cv2.INTER_LINEAR)
        warped_mask = cv2.warpAffine(mask, transform, (w, h), flags=cv2.INTER_LINEAR)
        alpha = warped_mask * visibility
        base = cleaned.astype(np.float32) * (1 - alpha[..., None])
        output = cv2.add(base, warped * visibility, dtype=cv2.CV_8U)
        if phase == State.APPEARING and complete:
            # A short whole-frame dissolve avoids silhouette fringes on return.
            # The person fades into place without stretching or flying sideways.
            output = cv2.addWeighted(background, 1 - visibility, frame, visibility, 0)
        if settings.glow <= 0:
            return cv2.resize(output, output_size) if output_size != (w, h) else output
        # Procedural VFX at reduced resolution: energy contour, displacement,
        # radial particles, horizontal speed trails and a localized light flash.
        scale = min(1.0, 640 / w)
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small_mask = cv2.resize(mask, (sw, sh))
        center = np.array([cx * scale, cy * scale])
        envelope = math.sin(math.pi * p) ** 0.7
        edge = cv2.morphologyEx(small_mask, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8))
        edge = cv2.GaussianBlur(edge, (17, 17), 4)
        light = np.zeros((sh, sw, 3), dtype=np.float32)
        light += edge[..., None] * np.array([240, 190, 100], np.float32) * 2
        particles = self._particles[:18] if phase == State.APPEARING else self._particles
        for a, distance, length, offset in particles:
            theta = a * math.tau
            radius = (0.05 + distance * 0.35 + p * 0.28) * sh
            point = center + np.array([math.cos(theta) * radius, math.sin(theta) * radius])
            x, y = int(point[0]), int(point[1])
            trail = int((0.02 + length * 0.13) * sw * envelope)
            if phase == State.APPEARING:
                cv2.line(light, (x, y - trail // 2), (x, y + 3), (180, 155, 80), 1, cv2.LINE_AA)
            else:
                cv2.line(light, (x - trail, y), (x + 3, y), (180, 155, 80), 1, cv2.LINE_AA)
            cv2.circle(light, (x, y), 1 + int(offset * 2), (255, 240, 200), -1, cv2.LINE_AA)
        yy, xx = np.ogrid[:sh, :sw]
        radial = np.exp(-(((xx - center[0]) / (sw * 0.25)) ** 2
                          + ((yy - center[1]) / (sh * 0.5)) ** 2) * 2)
        flash = math.exp(-((p - 0.45) / 0.16) ** 2)
        light += radial[..., None] * np.array([180, 210, 255]) * flash * 0.75
        light = cv2.resize(light, (w, h)) * envelope * settings.glow
        if phase == State.APPEARING:
            light *= 0.4
        # Sinusoidal spatial distortion peaks during the flash, fades at both ends.
        if phase == State.DISAPPEARING and flash * envelope > 0.2:
            small = cv2.resize(output, (sw, sh))
            grid_y, grid_x = np.mgrid[:sh, :sw].astype(np.float32)
            grid_x += (np.sin(grid_y * 0.12 + p * 25) * 6 * radial * flash).astype(np.float32)
            small = cv2.remap(small, grid_x, grid_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            output = cv2.resize(small, (w, h))
        output = cv2.add(output, light, dtype=cv2.CV_8U)
        return cv2.resize(output, output_size) if output_size != (w, h) else output
