"""Opt-in real-device probes, JSON evidence. No webcam frames are saved."""
import argparse
import json
from pathlib import Path
import sys
import time

# Allow direct invocation from tools/ without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from animecam.camera import Camera
from animecam.config import Settings
from animecam.virtual_camera import VirtualCamera


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, help="Open this physical camera and read real frames")
    parser.add_argument("--virtual", action="store_true", help="Send procedural test frames to the real OBS backend")
    parser.add_argument("--seconds", type=float, default=3)
    parser.add_argument("--report", type=Path, default=Path("artifacts/hardware-report.json"))
    args = parser.parse_args()
    report = {"python": sys.version, "opencv": cv2.__version__,
              "camera": "not_requested", "virtual": "not_requested",
              "call_app_receiver": "not_tested"}
    if args.camera is not None:
        camera = Camera(Settings(camera_index=args.camera))
        try:
            camera.open()
            start, sequence, count = time.monotonic(), 0, 0
            while time.monotonic() - start < args.seconds:
                item = camera.next_frame(sequence)
                if item:
                    sequence, _, frame = item
                    count += 1
                    report["camera_shape"] = list(frame.shape)
            if count == 0:
                raise RuntimeError("Camera opened but no frames arrived")
            report["camera"] = "passed_real_frame_read"
            report["camera_frames"] = count
        except Exception as exc:
            report["camera"] = "unavailable_or_failed"
            report["camera_error"] = str(exc)
        finally:
            try:
                camera.close()
            except Exception as exc:
                report["camera_close_error"] = str(exc)
    if args.virtual:
        virtual = VirtualCamera()
        try:
            report["virtual_device"] = virtual.start(640, 480, 30)
            for i in range(max(1, int(args.seconds * 30))):
                frame = np.zeros((480, 640, 3), np.uint8)
                frame[:] = (40, 50, 70)
                cv2.rectangle(frame, (i % 500, 80), (i % 500 + 100, 380), (100, 230, 180), -1)
                virtual.send(frame)
                time.sleep(1 / 30)
            report["virtual"] = "passed_real_backend_send"
            report["virtual_frames_sent"] = virtual.frames_sent
        except Exception as exc:
            report["virtual"] = "unavailable_or_failed"
            report["virtual_error"] = str(exc)
        finally:
            virtual.stop()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return int("unavailable_or_failed" in (report["camera"], report["virtual"]))


if __name__ == "__main__":
    raise SystemExit(main())
