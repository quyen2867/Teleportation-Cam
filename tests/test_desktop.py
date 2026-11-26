import time
import uuid
import subprocess
import sys

import pytest
from PySide6.QtWidgets import QApplication

import animecam.desktop as desktop


class Registry:
    HKEY_CURRENT_USER = "current-user"
    REG_SZ = 1

    def __init__(self):
        self.values = {}
        self.roots = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def OpenKey(self, root, key):
        self.roots.append((root, key))
        return self

    CreateKey = OpenKey

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError
        return self.values[name], self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError
        del self.values[name]


def test_startup_uses_only_current_user_and_never_starts_the_camera():
    registry = Registry()
    assert not desktop.startup_enabled(registry)
    desktop.set_startup(True, registry)
    assert desktop.startup_enabled(registry)
    command = registry.values[desktop.STARTUP_NAME]
    assert command.endswith(" --tray")
    assert "--start-camera" not in command and "--start-virtual-camera" not in command
    assert all(root == registry.HKEY_CURRENT_USER and key == desktop.STARTUP_KEY for root, key in registry.roots)
    desktop.set_startup(False, registry)
    desktop.set_startup(False, registry)
    assert not desktop.startup_enabled(registry)


def test_startup_quotes_installed_executable_paths_with_spaces(monkeypatch):
    monkeypatch.setattr(desktop.sys, "executable", r"C:\Program Files\AnimeCam FX\AnimeCamFX.exe")
    monkeypatch.setattr(desktop.sys, "frozen", True, raising=False)
    assert desktop.launch_command(["--tray"]) == '"C:\\Program Files\\AnimeCam FX\\AnimeCamFX.exe" --tray'


def test_idle_launch_and_removed_meeting_destinations():
    assert desktop.validated_request({"show": False}) == {"show": False, "camera": False, "virtual": False}
    with pytest.raises(ValueError):
        desktop.validated_request({"meeting": "meet"})
    with pytest.raises(ValueError):
        desktop.validated_request({"meeting": "https://untrusted.example"})
    with pytest.raises(ValueError):
        desktop.validated_request({"camera": "false"})


def test_repeat_shortcut_click_is_forwarded_over_real_local_ipc():
    app = QApplication.instance() or QApplication([])
    name = "AnimeCamFX-test-" + uuid.uuid4().hex[:8]
    server = desktop.InstanceBroker(name)
    received = []
    server.received.connect(received.append)
    server.listen()
    code = (
        "import sys; from PySide6.QtCore import QCoreApplication; "
        "from animecam.desktop import InstanceBroker; app=QCoreApplication([]); "
        "client=InstanceBroker(sys.argv[1]); "
        "ok=client.forward({'show':True,'camera':True,'virtual':True}); "
        "print(ok); sys.exit(0 if ok else 1)"
    )
    sender = subprocess.Popen([sys.executable, "-c", code, name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Use a real second process: Qt's blocking pipe write can hold the GIL,
        # preventing a Python receiver in the same interpreter from accepting.
        deadline = time.monotonic() + 10
        while (not received or sender.poll() is None) and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        output, error = sender.communicate(timeout=2)
        assert sender.returncode == 0, (output, error)
        assert received == [{"show": True, "camera": True, "virtual": True}]
    finally:
        if sender.poll() is None:
            sender.terminate()
        server.close()


def test_macos_startup_writes_only_a_launch_agent(tmp_path, monkeypatch):
    import plistlib

    path = tmp_path / "com.animecamfx.tray.plist"
    applied = []
    monkeypatch.setattr(desktop, "launch_agent_path", lambda: path)
    monkeypatch.setattr(desktop, "_launchctl", applied.append)

    desktop._set_macos_startup(True)
    payload = plistlib.loads(path.read_bytes())
    assert payload["Label"] == desktop.LAUNCH_AGENT_ID
    assert payload["RunAtLoad"] is True
    assert payload["ProgramArguments"][-1] == "--tray"
    assert "--start-camera" not in payload["ProgramArguments"]
    assert "--start-virtual-camera" not in payload["ProgramArguments"]
    assert applied == [True]

    desktop._set_macos_startup(False)
    assert not path.exists()
    assert applied == [True, False]


def test_macos_startup_state_follows_the_launch_agent(tmp_path, monkeypatch):
    if desktop.sys.platform != "darwin":
        pytest.skip("macOS launch agent")
    path = tmp_path / "com.animecamfx.tray.plist"
    monkeypatch.setattr(desktop, "launch_agent_path", lambda: path)
    assert not desktop.startup_enabled()
    path.write_text("{}", encoding="utf-8")
    assert desktop.startup_enabled()
