# -*- mode: python ; coding: utf-8 -*-
"""Lean desktop release: no developer entry point, guides, or video-file decoder."""
import os
import re
from pathlib import Path
from importlib.metadata import distribution

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPECPATH).parent
name = os.environ.get("ANIMECAM_BUILD_NAME", "AnimeCamFX")
if not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,60}", name):
    raise ValueError("Invalid build name")

datas = [(str(root / "models"), "models")]
for asset in ("animecam.ico", "goku-instant-transmission.mp3", "sound-source.json", "check.svg", "up.svg", "down.svg"):
    datas.append((str(root / "assets" / asset), "assets"))
datas.append((str(root / "THIRD_PARTY_NOTICES.md"), "licenses"))
# Keep dependency license texts, rather than shipping development documentation.
for package in ("mediapipe", "opencv-contrib-python", "numpy", "PySide6-Essentials", "shiboken6",
                "pyvirtualcam", "sounddevice", "soundfile", "matplotlib", "pillow", "contourpy",
                "kiwisolver", "fonttools", "packaging", "pyparsing", "python-dateutil", "six",
                "cffi", "pycparser", "cycler"):
    dist = distribution(package)
    for file in dist.files or ():
        if any(part.lower().startswith(("license", "copying", "notice")) for part in file.parts):
            source = Path(dist.locate_file(file))
            if source.is_file():
                datas.append((str(source), f"licenses/{package}/{file.parent.as_posix()}"))
datas += collect_data_files("mediapipe", excludes=["**/test*", "**/__pycache__/*"])

a = Analysis(
    [str(root / "launcher.py")], pathex=[str(root)],
    binaries=[*collect_dynamic_libs("mediapipe"),
              (str(root / "artifacts/native/shared_camera.dll"), "native")], datas=datas,
    hiddenimports=["pyvirtualcam._native_windows_obs"],
    hookspath=[], hooksconfig={"matplotlib": {"backends": ["Agg"]}}, runtime_hooks=[],
    excludes=["tensorflow", "torch", "IPython", "pytest", "tools", "tests", "tkinter"],
    noarchive=False, optimize=1,
)
# DirectShow / Media Foundation webcam capture does not use the separate FFmpeg
# plugin. The app has no video-file playback or recording feature.
a.binaries = [entry for entry in a.binaries if not Path(entry[0]).name.lower().startswith("opencv_videoio_ffmpeg")]
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name=name,
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=str(root / "assets" / "animecam.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=name)
