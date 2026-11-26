"""Explicit, atomic model installation. No network access during camera use."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

from animecam.config import resource_root

MODELS = {
    "hand_landmarker.task": "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter_landscape/float16/1/selfie_segmenter_landscape.tflite",
}


def model_paths(directory: Path | None = None) -> dict[str, Path]:
    directory = directory or resource_root() / "models"
    paths = {name: directory / name for name in MODELS}
    missing = [p.name for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            "Thiếu mô hình AI: " + ", ".join(missing)
            + (". Hãy cài lại ứng dụng." if getattr(sys, "frozen", False)
               else ". Chạy lệnh: python -m animecam.models --download")
        )
    manifest = resource_root() / "models" / "checksums.json"
    if manifest.is_file():
        hashes = json.loads(manifest.read_text(encoding="utf-8"))
        for name, path in paths.items():
            if name in hashes and hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
                raise ValueError(f"Mô hình {name} không đúng mã kiểm tra. Hãy tải lại mô hình.")
    return paths


def download(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = resource_root() / "models" / "checksums.json"
    hashes = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {}
    for name, url in MODELS.items():
        target = directory / name
        if target.is_file() and name in hashes:
            if hashlib.sha256(target.read_bytes()).hexdigest() == hashes[name]:
                print(f"Verified {name}", flush=True)
                continue
        temporary = target.with_suffix(".part")
        print(f"Downloading {name} from Google MediaPipe models…", flush=True)
        try:
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
            if name in hashes and digest != hashes[name]:
                raise ValueError(f"Checksum mismatch: {name}")
            temporary.replace(target)
            print(f"SHA256 {name}: {digest}", flush=True)
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    parser.add_argument("--directory", type=Path, default=resource_root() / "models")
    args = parser.parse_args()
    download(args.directory)


if __name__ == "__main__":
    main()
