"""Rasterize our source SVG for Windows' multi-size application icon."""
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main():
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    renderer = QSvgRenderer(str(assets / "animecam.svg"))
    if not renderer.isValid():
        raise RuntimeError("Invalid application SVG")
    bitmap = QImage(256, 256, QImage.Format.Format_ARGB32)
    bitmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(bitmap)
    renderer.render(painter)
    painter.end()
    bitmap.save(str(assets / "animecam.png"))
    with Image.open(assets / "animecam.png") as image:
        image.save(assets / "animecam.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("Created assets/animecam.ico")


if __name__ == "__main__":
    main()
