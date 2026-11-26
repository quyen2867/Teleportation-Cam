"""Real two-process camera sharing probe. Reports metrics only; no frames saved."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
from animecam.camera import Camera
from animecam.config import Settings


def child(mode, directory, name, index):
    ready, stop = directory / f"{name}.ready", directory / "stop"
    report = {"mode": mode, "frames": 0, "overlap_frames": 0}
    device = None
    started = time.monotonic()
    try:
        if mode == "shared":
            device = Camera(Settings(camera_index=index))
            device.open()
        else:
            device = cv2.VideoCapture(index, cv2.CAP_MSMF if mode == "msmf" else cv2.CAP_DSHOW)
            if not device.isOpened():
                raise RuntimeError("Second camera client could not open the device")
        sequence = 0
        means = []
        while not stop.exists() and time.monotonic() - started < 25:
            if mode == "shared":
                item = device.next_frame(sequence)
                if item is None:
                    continue
                sequence, _, frame = item
            else:
                ok, frame = device.read()
                if not ok:
                    raise RuntimeError("Second camera client stopped returning frames")
            report["frames"] += 1
            report["shape"] = list(frame.shape)
            if (directory / "overlap").exists():
                report["overlap_frames"] += 1
                means.append(float(frame.mean()))
            if report["frames"] >= 5:
                ready.touch()
        if means:
            report["overlap_mean_range"] = [min(means), max(means)]
            report["nonblack_overlap_frames"] = sum(value > 1 for value in means)
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        if device is not None:
            try:
                device.close() if mode == "shared" else device.release()
            except Exception as exc:
                report["cleanup_error"] = str(exc)
        (directory / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def wait_ready(process, path):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline and process.poll() is None:
        if path.exists():
            return True
        time.sleep(0.05)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=["shared", "msmf", "dshow"])
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.directory, args.name, args.camera)
        return
    root = Path("artifacts") / f"camera-sharing-{time.time_ns()}"
    root.mkdir(parents=True)
    reports = []
    for n, modes in enumerate((("shared", "msmf"), ("msmf", "shared"), ("shared", "dshow"), ("dshow", "shared"))):
        folder = root / str(n)
        folder.mkdir()
        children = []
        logs = []
        try:
            for name, mode in zip(("first", "second"), modes):
                log = (folder / f"{name}.log").open("w", encoding="utf-8")
                logs.append(log)
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", mode,
                                            "--directory", str(folder.resolve()), "--name", name,
                                            "--camera", str(args.camera)], stdout=log, stderr=log)
                children.append(process)
                if not wait_ready(process, folder / f"{name}.ready"):
                    break
            (folder / "overlap").touch()
            time.sleep(2)
        finally:
            (folder / "stop").touch()
            for process in children:
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.terminate()  # Only our probe process; never a user app.
                    process.wait(timeout=3)
            for log in logs:
                log.close()
        result = {"order": list(modes)}
        for name in ("first", "second"):
            path = folder / f"{name}.json"
            result[name] = json.loads(path.read_text()) if path.is_file() else {"error": "No report (timeout or not started)"}
        result["passed"] = all(result[name].get("nonblack_overlap_frames", 0) >= 10 for name in ("first", "second"))
        reports.append(result)
    target = Path("artifacts/camera-sharing-0.4.0.json")
    target.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
