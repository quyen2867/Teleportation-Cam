from PySide6.QtWidgets import QApplication

from animecam.ui import MainWindow, apply_theme


def test_controls_update_real_settings_and_camera_controls_are_guarded():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(persist=False)
    assert tuple(window.resolution.currentData()) == (1280, 720)
    assert window.complete_hide.isChecked() and window.settings.complete_hide
    assert window.camera_button.text() == "Bật camera"
    assert window.hide_button.text() == "Ẩn ngay (F10)"
    assert window.quick_disappear.isChecked() and not window.disappear.isEnabled()
    assert window.sound_enabled.isChecked()
    window.glow_slider.setValue(125)
    window.sensitivity.setValue(80)
    window.disappear.setValue(0.65)
    window.appear.setValue(0.9)
    window.quality.setCurrentIndex(1)
    window.enabled.setChecked(False)
    window.mirror.setChecked(False)
    assert window.settings.glow == 1.25
    assert window.settings.sensitivity == 0.8
    assert window.settings.disappear_seconds == 0.65
    assert window.settings.appear_seconds == 0.9
    assert window.settings.segmentation_every == 2
    assert not window.settings.enabled and not window.settings.mirror
    assert not window.virtual_button.isEnabled()
    assert not window.capture_button.isEnabled()
    assert not window.hide_button.isEnabled()
    window.close()


def test_vietnamese_sound_and_return_controls_update_real_settings():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(persist=False)
    window.quick_disappear.setChecked(False)
    assert not window.settings.quick_disappear and window.disappear.isEnabled()
    window.volume.setValue(45)
    window.sound_enabled.setChecked(False)
    assert window.settings.sound_volume == 0.45 and not window.settings.sound_enabled
    played = []
    window.sound.play = lambda volume, device, path: played.append((volume, device, path))
    window._play_sound()  # disabled: returning from the effect must stay silent
    assert not played
    window._play_sound(preview=True)
    assert played == [(0.45, -1, "")]
    window.close()


def test_automatic_background_and_sound_file_controls_are_wired():
    from types import SimpleNamespace

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(persist=False)
    assert window.auto_background.isChecked() and window.settings.auto_background
    assert "Goku Instant Transmission" in window.sound_file_label.text()
    assert not window.auto_capture_button.isEnabled()
    window.auto_background.setChecked(False)
    assert not window.settings.auto_background
    window._change(sound_file="C:/test/custom.wav")
    window._default_sound()
    assert window.settings.sound_file == ""
    commands = []
    window.worker = SimpleNamespace(configure=lambda **changes: None, command=commands.append)
    window._command("auto_capture")
    assert window.settings.auto_background and commands == ["auto_capture"]
    window.worker = None
    window.close()


def test_hide_button_enables_complete_mode_and_dispatches_real_command():
    from types import SimpleNamespace

    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    window = MainWindow(persist=False)
    window.enabled.setChecked(False)
    window.complete_hide.setChecked(False)
    commands = []
    window.worker = SimpleNamespace(configure=lambda **changes: None, command=commands.append)
    window._command("hide")
    assert window.settings.complete_hide and window.settings.enabled
    assert commands == ["hide"]
    window.worker = None
    window.close()


def test_output_starts_once_and_receives_processed_frames():
    from types import SimpleNamespace
    import numpy as np

    app = QApplication.instance() or QApplication([])
    window = MainWindow(persist=False)
    commands = []
    frame = np.zeros((120, 160, 3), np.uint8)
    packet = SimpleNamespace(frame=frame, output=frame, fps=30, inference_ms=1, latency_ms=2,
                             state="VISIBLE", gesture="Test", score=0, progress=0, background="Test",
                             background_ready=False, warning="", virtual=True, frames_sent=1)
    window.worker = SimpleNamespace(command=commands.append, take_packet=lambda: packet)
    window.start_output()
    window.start_output()
    assert commands == ["virtual_start"]
    window._poll()
    window._poll()
    assert not window.video.image.isNull()
    assert "đang bật" in window.virtual_label.text()
    window.worker = None
    window.close()
    app.processEvents()


def test_startup_checkbox_is_explicit_and_uses_the_platform_integration(monkeypatch):
    import animecam.ui as module

    app = QApplication.instance() or QApplication([])
    writes = []
    monkeypatch.setattr(module, "startup_enabled", lambda: False)
    monkeypatch.setattr(module, "set_startup", writes.append)
    window = MainWindow(persist=False)
    assert not window.startup.isChecked() and not writes
    window.startup.setChecked(True)
    window.startup.setChecked(False)
    assert writes == [True, False]
    window.close()
    app.processEvents()


def test_camera_mode_controls_follow_the_platform(monkeypatch):
    import animecam.ui as module

    app = QApplication.instance() or QApplication([])
    opened = []
    monkeypatch.setattr(module, "Pipeline", lambda *args: opened.append(args))
    window = MainWindow(persist=False)
    assert not opened and window.worker is None
    if module.IS_WINDOWS:
        assert window.settings.camera_mode == "shared"
        assert not window.resolution.isEnabled() and not window.fps_spin.isEnabled()
        window.camera_mode.setCurrentIndex(window.camera_mode.findData("compatibility"))
    else:
        # Shared Frame Server capture is Windows-only.
        assert window.camera_mode.findData("shared") == -1
        assert window.settings.camera_mode == "compatibility"
    assert window.settings.camera_mode == "compatibility"
    assert window.resolution.isEnabled() and window.fps_spin.isEnabled()
    assert not opened
    window.close()
    app.processEvents()
