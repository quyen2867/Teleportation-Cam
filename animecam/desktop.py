"""Windows desktop integration. Importing this module never changes Windows."""
import getpass
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from animecam.config import resource_root

STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_NAME = "AnimeCamFX"


def launch_command(arguments=()):
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(resource_root() / "main.py"))
    return subprocess.list2cmdline([*command, *arguments])


def startup_enabled(registry=None):
    if sys.platform != "win32" and registry is None:
        return False
    if registry is None:
        import winreg as registry
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, STARTUP_KEY) as key:
            value, _ = registry.QueryValueEx(key, STARTUP_NAME)
            return bool(value)
    except OSError:
        return False


def set_startup(enabled, registry=None):
    if sys.platform != "win32" and registry is None:
        raise RuntimeError("Khởi động cùng Windows chỉ dùng được trên Windows")
    if registry is None:
        import winreg as registry
    # This Run value opens an idle tray app. It never starts the webcam at login.
    with registry.CreateKey(registry.HKEY_CURRENT_USER, STARTUP_KEY) as key:
        if enabled:
            registry.SetValueEx(key, STARTUP_NAME, 0, registry.REG_SZ, launch_command(["--tray"]))
        else:
            try:
                registry.DeleteValue(key, STARTUP_NAME)
            except FileNotFoundError:
                pass


def validated_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Invalid launch request")
    if payload.get("meeting") is not None:
        raise ValueError("Meeting shortcuts are no longer supported")
    for field in ("show", "camera", "virtual"):
        if field in payload and not isinstance(payload[field], bool):
            raise ValueError("Invalid launch flag")
    return {"show": bool(payload.get("show", True)),
            "camera": bool(payload.get("camera", False)),
            "virtual": bool(payload.get("virtual", False))}


class InstanceBroker(QObject):
    """Forward repeat shortcut clicks to the existing current-user process."""
    received = Signal(dict)

    def __init__(self, name=None, parent=None):
        super().__init__(parent)
        identity = f"{getpass.getuser()}|{Path.home()}".encode("utf-8")
        self.name = name or "AnimeCamFX-" + hashlib.sha256(identity).hexdigest()[:16]
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        self._buffers = {}

    def forward(self, payload):
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(200):
            return False
        socket.write(json.dumps(validated_request(payload)).encode("utf-8") + b"\n")
        socket.flush()
        sent = socket.bytesToWrite() == 0 or socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return sent

    def listen(self):
        if not self.server.listen(self.name):
            raise RuntimeError("Không tạo được phiên ứng dụng. Hãy mở AnimeCam FX đang chạy ở khay hệ thống.")

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self._buffers[socket] = bytearray()
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._drop(s))
            self._read(socket)

    def _drop(self, socket):
        self._buffers.pop(socket, None)
        socket.deleteLater()

    def _read(self, socket):
        buffer = self._buffers.get(socket)
        if buffer is None:
            return
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > 4096:
            socket.abort()
            return
        if b"\n" not in buffer:
            return
        try:
            payload = validated_request(json.loads(bytes(buffer).split(b"\n", 1)[0]))
        except (ValueError, TypeError, UnicodeError):
            socket.abort()
            return
        self.received.emit(payload)
        socket.disconnectFromServer()

    def close(self):
        for socket in list(self._buffers):
            socket.abort()
        self.server.close()
