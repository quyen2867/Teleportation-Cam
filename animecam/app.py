"""Desktop application entry point; development tools are kept out of releases."""
import argparse
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def main(arguments=None, *, ui_smoke=False, screenshot=None):
    parser = argparse.ArgumentParser(description="AnimeCam FX")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--start-camera", action="store_true")
    parser.add_argument("--start-virtual-camera", action="store_true")
    parser.add_argument("--ui-smoke", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--screenshot", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(arguments)
    ui_smoke = ui_smoke or args.ui_smoke
    screenshot = screenshot or args.screenshot
    from PySide6.QtCore import QStandardPaths, QTimer
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from animecam.ui import MainWindow, apply_theme
    from animecam.config import resource_root
    from animecam.desktop import InstanceBroker

    app = QApplication([sys.argv[0]])
    app.setApplicationName("AnimeCamFX")
    app.setOrganizationName("AnimeCamFX")
    app.setWindowIcon(QIcon(str(resource_root() / "assets" / "animecam.ico")))
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AnimeCamFX.Desktop")
    log_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    # Smoke tests write only into the workspace.
    if ui_smoke:
        log_dir = Path("artifacts")
    log_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(log_dir / "matplotlib"))
    handler = RotatingFileHandler(log_dir / "animecam.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s %(message)s")
    apply_theme(app)
    request = {"show": not args.tray, "camera": args.start_camera or args.start_virtual_camera,
               "virtual": args.start_virtual_camera}
    broker = None
    if not ui_smoke:
        broker = InstanceBroker()
        if broker.forward(request):
            return 0
        broker.listen()
    window = MainWindow(persist=not ui_smoke, desktop_mode=not ui_smoke)
    if broker:
        broker.received.connect(window.apply_launch_request)
        app.aboutToQuit.connect(broker.close)
    if not args.tray or not window.has_tray:
        window.show()
    if not ui_smoke:
        QTimer.singleShot(0, lambda: window.apply_launch_request(request))
    if ui_smoke:
        def finish():
            if screenshot:
                screenshot.parent.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(screenshot))
            window.close()
        QTimer.singleShot(800, finish)
    return app.exec()
