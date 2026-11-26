import os
from pathlib import Path

# Keep matplotlib's imported-by-MediaPipe cache in the writable test workspace.
cache = Path(__file__).resolve().parents[1] / "artifacts" / "matplotlib"
cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(cache))
