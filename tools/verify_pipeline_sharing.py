"""Pipeline/OBS and another real camera client concurrently; no frames saved."""
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QTimer
from animecam.config import Settings
from animecam.pipeline import Pipeline


def main():
    folder = Path("artifacts") / f"pipeline-sharing-{time.time_ns()}"
    folder.mkdir(parents=True)
    app = QCoreApplication([])
    worker = Pipeline(Settings())
    report = {"scope": "real shared camera -> AI -> OBS while second process uses physical webcam",
              "errors": [], "packets": 0, "virtual_frames": 0, "output_sizes": []}
    worker.error.connect(report["errors"].append)
    client = None
    log = (folder / "client.log").open("w", encoding="utf-8")
    start = time.monotonic()

    def poll():
        nonlocal client
        packet = worker.take_packet()
        if packet:
            report["packets"] += 1
            report["virtual_frames"] = packet.frames_sent
            size = list(packet.output.shape)
            if size not in report["output_sizes"]:
                report["output_sizes"].append(size)
            if report["packets"] == 10:
                client = subprocess.Popen([sys.executable, "tools/verify_camera_sharing.py", "--child", "msmf",
                                           "--directory", str(folder.resolve()), "--name", "client"],
                                          stdout=log, stderr=log)
                (folder / "overlap").touch()
            if (folder / "client.ready").exists() and report["packets"] > 150:
                worker.stop()
        if time.monotonic() - start > 25:
            worker.stop()

    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(16)
    worker.finished.connect(app.quit)
    worker.command("virtual_start")
    worker.start()
    app.exec()
    worker.wait()
    (folder / "stop").touch()
    if client:
        try:
            client.wait(timeout=6)
        except subprocess.TimeoutExpired:
            client.terminate()
            client.wait(timeout=3)
    log.close()
    path = folder / "client.json"
    report["second_client"] = json.loads(path.read_text()) if path.is_file() else {"error": "No report"}
    report["passed"] = (not report["errors"] and report["virtual_frames"] > 100
                        and len(report["output_sizes"]) == 1
                        and report["second_client"].get("nonblack_overlap_frames", 0) > 50)
    Path("artifacts/pipeline-sharing-0.4.0.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    sys.exit(main())
