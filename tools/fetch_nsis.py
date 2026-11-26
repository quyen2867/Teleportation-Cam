"""Fetch a pinned portable compiler from the official NSIS SourceForge project."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

URL = "https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip"
SHA256 = "56581f90db321581c5381193d796fffcf2d24b2f8fed2160a6c6a3baa67f2c4f"


def main():
    root = (Path(__file__).resolve().parents[1] / "artifacts" / "toolchain").resolve()
    root.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(12_000_001)
    if len(data) > 12_000_000 or hashlib.sha256(data).hexdigest() != SHA256:
        raise RuntimeError("NSIS archive checksum mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            if not (root / member.filename).resolve().is_relative_to(root) or member.file_size > 20_000_000:
                raise RuntimeError("Unsafe archive path or size")
        archive.extractall(root)
    print(root / "nsis-3.12" / "makensis.exe")


if __name__ == "__main__":
    main()
