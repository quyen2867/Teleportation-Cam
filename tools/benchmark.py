"""Synthetic render benchmark only; never a webcam/end-to-end FPS claim."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from animecam.config import Settings
from animecam.effects import InstantTransmission


def main():
    cv2.setNumThreads(2)
    bg = np.full((720, 1280, 3), (35, 40, 45), np.uint8)
    frame = bg.copy()
    mask = np.zeros((720, 1280), np.float32)
    cv2.ellipse(mask, (640, 410), (150, 290), 0, 0, 360, 1, -1)
    frame[mask > 0.5] = (160, 180, 200)
    settings = Settings()
    result = {"scope": "Synthetic 1280x720 rendering; excludes camera, AI, GUI, and receiver latency"}
    for phase in ("visible", "transition", "hidden"):
        times = []
        effect = InstantTransmission()
        for _ in range(5):
            effect.render(frame, mask, bg, 0, settings)
        for i in range(90):
            effect.restore()
            if phase != "visible":
                effect.trigger(0, True)
            timestamp = (i % 30) / 60 if phase == "transition" else 1
            start = time.perf_counter()
            effect.render(frame, mask, bg, timestamp, settings)
            times.append((time.perf_counter() - start) * 1000)
        result[phase] = {"median_ms": round(float(np.median(times)), 2),
                         "p95_ms": round(float(np.percentile(times, 95)), 2)}
    target = Path("artifacts/benchmark.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
