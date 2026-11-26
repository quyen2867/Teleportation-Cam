"""Read real webcam -> real CPU Tasks -> compositor -> optional real OBS output.

No frames are saved. Does not claim a human performed the teleport gesture.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/matplotlib").resolve()))

from PySide6.QtCore import QCoreApplication, QTimer

from animecam.camera import Camera
from animecam.config import Settings
from animecam.pipeline import Pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--virtual", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("artifacts/live-smoke.json"))
    args = parser.parse_args(argv)
    app = QCoreApplication([])
    settings = Settings(camera_index=args.camera)
    worker = Pipeline(settings)
    errors, packets, metrics = [], 0, []
    first = None
    last_sent = 0
    report = {"scope": "Real webcam -> CPU Tasks -> visible compositor -> OBS when requested",
              "gesture_on_human": "not_tested", "call_app_receiver": "not_tested"}
    worker.error.connect(errors.append)
    if args.virtual:
        worker.command("virtual_start")

    def poll():
        nonlocal packets, first, last_sent
        packet = worker.take_packet()
        if packet:
            packets += 1
            first = first or time.monotonic()
            metrics.append([packet.fps, packet.inference_ms, packet.latency_ms])
            last_sent = packet.frames_sent
            report["resolution"] = [packet.frame.shape[1], packet.frame.shape[0]]
            if time.monotonic() - first >= args.seconds:
                worker.stop()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(16)
    worker.finished.connect(app.quit)
    QTimer.singleShot(int((args.seconds + 25) * 1000), worker.stop)
    worker.start()
    app.exec()
    worker.wait()
    import numpy as np
    report.update(packets_observed=packets, virtual_frames_sent=last_sent, errors=errors)
    if metrics:
        values = np.asarray(metrics)[1:]
        if len(values):
            report["median_fps"] = round(float(np.median(values[:, 0])), 2)
            report["median_ai_ms"] = round(float(np.median(values[:, 1])), 2)
            report["median_frame_age_ms"] = round(float(np.median(values[:, 2])), 2)
    # Verify a new reader can reacquire the device after the pipeline closes it.
    camera = Camera(settings)
    try:
        camera.open()
        report["camera_reopened_after_stop"] = camera.next_frame(0, timeout=3) is not None
    except Exception as exc:
        report["camera_reopened_after_stop"] = False
        errors.append(str(exc))
    finally:
        camera.close()
    target = args.report
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return int(bool(errors) or packets == 0 or (args.virtual and last_sent == 0))


if __name__ == "__main__":
    raise SystemExit(main())
