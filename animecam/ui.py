from dataclasses import asdict, replace
from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, Signal, QLocale, QSignalBlocker
from PySide6.QtGui import QColor, QImage, QPainter, QShortcut, QKeySequence, QIcon, QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider,
    QSpinBox, QVBoxLayout, QWidget, QTabWidget, QFileDialog, QSystemTrayIcon, QMenu, QToolTip,
)

from animecam.config import Settings, resource_root
from animecam import __version__
from animecam.pipeline import Pipeline
from animecam.sound import SoundPlayer
from animecam.desktop import startup_enabled, set_startup, validated_request


FONT_FAMILY = "Calibri"

STYLE = """
QWidget { font-family: 'Calibri'; font-size: 15px; color: #242424; }
QMainWindow, QDialog { background: #f3f3f3; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#muted { color: #666666; }
QLabel#section { font-weight: 600; }
QLabel#badge { color: #444444; }
QFrame#panel { background: transparent; border: none; }
QPushButton { background: #fafafa; border: 1px solid #c8c8c8; border-radius: 3px; padding: 7px 13px; }
QPushButton:hover { background: #ffffff; border-color: #8a8a8a; }
QPushButton:pressed { background: #e7e7e7; }
QPushButton:focus { border-color: #2667a9; }
QPushButton:disabled { color: #939393; background: #efefef; border-color: #dadada; }
QPushButton#primary { color: #ffffff; background: #285f96; border-color: #285f96; }
QPushButton#primary:hover { background: #3472ad; }
QPushButton#primary:disabled { color: #8c8c8c; background: #e7e7e7; border-color: #d4d4d4; }
QPushButton#quiet { background: transparent; border-color: transparent; padding: 5px 8px; }
QPushButton#quiet:hover { background: #e6e6e6; border-color: #d2d2d2; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #c5c5c5; border-radius: 2px; padding: 5px; min-height: 23px; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { background: #ededed; color: #8b8b8b; }
QComboBox QAbstractItemView { background: #ffffff; color: #242424; selection-background-color: #dbe9f5; selection-color: #242424; }
QComboBox::drop-down { border: none; width: 25px; }
QComboBox::down-arrow { image: url("__ASSETS__/down.svg"); width: 10px; height: 6px; }
QSpinBox, QDoubleSpinBox { padding-right: 24px; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; background: #f5f5f5; border: 1px solid #d0d0d0; border-bottom: none; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; background: #f5f5f5; border: 1px solid #d0d0d0; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url("__ASSETS__/up.svg"); width: 8px; height: 5px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url("__ASSETS__/down.svg"); width: 8px; height: 5px; }
QCheckBox { spacing: 8px; background: transparent; min-height: 24px; }
QCheckBox::indicator { width: 14px; height: 14px; background: #ffffff; border: 1px solid #8b8b8b; border-radius: 2px; }
QCheckBox::indicator:checked { background: #285f96; border-color: #285f96; image: url("__ASSETS__/check.svg"); }
QCheckBox::indicator:hover { border-color: #285f96; }
QProgressBar { background: #dddddd; border: none; max-height: 3px; }
QProgressBar::chunk { background: #285f96; }
QSlider::groove:horizontal { height: 3px; background: #d2d2d2; }
QSlider::sub-page:horizontal { background: #285f96; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; background: #ffffff; border: 1px solid #7d7d7d; border-radius: 2px; }
QScrollArea { border: none; background: #ffffff; }
QWidget#settingsPage { background: #ffffff; }
QTabWidget::pane { border: 1px solid #d0d0d0; background: #ffffff; top: -1px; }
QTabBar::tab { background: #e9e9e9; border: 1px solid #d0d0d0; border-bottom: none; padding: 8px 12px; margin-right: 2px; }
QTabBar::tab:selected { background: #ffffff; }
QTabBar::tab:hover:!selected { background: #f8f8f8; }
QScrollBar:vertical { background: #f4f4f4; width: 9px; }
QScrollBar::handle:vertical { background: #b8b8b8; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu { background: #ffffff; border: 1px solid #cccccc; padding: 4px; }
QMenu::item { padding: 6px 22px; }
QMenu::item:selected { background: #e3edf6; }
QToolTip { background: #ffffff; color: #242424; border: 1px solid #bbbbbb; padding: 4px; }
"""


def label(text, kind=None, wrap=False):
    widget = QLabel(text)
    if kind:
        widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    return widget


def button(text, slot, kind=None):
    widget = QPushButton(text)
    if kind:
        widget.setObjectName(kind)
    widget.clicked.connect(slot)
    return widget


def card(title, caption=None):
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    layout.addWidget(label(title, "section"))
    if caption:
        layout.addWidget(label(caption, "muted", True))
    return frame, layout


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.setMinimumSize(256, 144)

    def set_frame(self, bgr):
        h, w = bgr.shape[:2]
        # QImage must own its memory beyond the lifetime of a worker packet.
        self.image = QImage(bgr.data, w, h, bgr.strides[0], QImage.Format.Format_BGR888).copy()
        self.update()

    def clear(self):
        self.image = QImage()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#202020"))
        if not self.image.isNull():
            scaled = self.image.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            x, y = (self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2
            painter.drawImage(self.rect().adjusted(x, y, -x, -y), self.image)
            return
        painter.setPen(QColor("#b0b0b0"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Bật camera để xem trước")


class OutputWindow(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("AnimeCam FX — Hình xuất sạch")
        self.resize(960, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.video = VideoView()
        layout.addWidget(self.video)


class MainWindow(QMainWindow):
    audio_error = Signal(str)

    def __init__(self, persist=True, desktop_mode=False):
        super().__init__()
        self.setWindowTitle(f"AnimeCam FX {__version__}")
        self.resize(1180, 740)
        self.setMinimumSize(1000, 680)
        self.preferences = QSettings("AnimeCamFX", "AnimeCamFX") if persist else None
        self.settings = self._load()
        self.worker = None
        self._closing = False
        self._quitting = False
        self._desktop_mode = desktop_mode
        self.tray = None
        self._tray_hint_shown = False
        self._virtual_requested = False
        self.sound = SoundPlayer(on_error=self.audio_error.emit)
        self.audio_error.connect(self._error)
        self.output_window = OutputWindow(self)
        self._build()
        self._setup_tray()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(16)
        for key, command in (("F8", "restore"), ("F9", "trigger"), ("F10", "hide"), ("Ctrl+B", "capture")):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda c=command: self._command(c))

    def _load(self):
        settings = Settings()
        if self.preferences:
            values = {}
            try:
                for name, default in asdict(settings).items():
                    values[name] = self.preferences.value(name, default, type=type(default))
                settings = Settings(**values)
            except (TypeError, ValueError):
                pass
        return settings

    def _change(self, **changes):
        self.settings = replace(self.settings, **changes)
        if self.worker is not None:
            self.worker.configure(**changes)
        if self.preferences:
            for name, value in changes.items():
                self.preferences.setValue(name, value)

    def _build(self):
        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(18, 14, 18, 10)
        root.setSpacing(14)
        header = QHBoxLayout()
        self.camera_button = button("Bật camera", self._toggle_camera, "primary")
        header.addWidget(self.camera_button)
        self.virtual_button = button("Bật camera ảo", self._toggle_virtual)
        self.virtual_button.setToolTip("Cần OBS Studio. Chọn OBS Virtual Camera trong ứng dụng gọi video.\nKhông bật camera ảo trong OBS cùng lúc.")
        header.addWidget(self.virtual_button)
        header.addStretch()
        header.addWidget(button("Trợ giúp", self._help, "quiet"))
        header.addWidget(button("Thoát", self.request_quit, "quiet"))
        root.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(12)
        preview_card, pv = card("Xem trước")
        pv.itemAt(0).widget().hide()
        preview_header = QHBoxLayout()
        self.live_label = label("Camera đang tắt", "muted")
        self.live_label.hide()
        self.metrics = label("", "muted")
        preview_header.addWidget(label("Xem trước", "section"))
        preview_header.addStretch()
        preview_header.addWidget(self.metrics)
        pv.addLayout(preview_header)
        self.video = VideoView()
        pv.addWidget(self.video, 1)
        bottom = QHBoxLayout()
        self.state_label = label("Camera đang tắt", "muted")
        bottom.addWidget(self.state_label)
        bottom.addStretch()
        bottom.addWidget(button("Hình xuất", self.output_window.show, "quiet"))
        pv.addLayout(bottom)
        left.addWidget(preview_card, 1)
        gesture_card, gl = card("Điều khiển")
        row = QHBoxLayout()
        self.gesture_label = label("Đang chờ camera", "muted", True)
        row.addWidget(self.gesture_label, 1)
        self.score_label = label("0%", "muted")
        self.score_label.hide()
        row.addWidget(self.score_label)
        gl.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        gl.addWidget(self.progress)
        controls = QHBoxLayout()
        self.teleport_button = button("Dịch chuyển (F9)", lambda: self._command("trigger"))
        self.restore_button = button("Hiện ngay (F8)", lambda: self._command("restore"))
        self.restore_button.setToolTip("Hiện lại ngay, bỏ qua hiệu ứng và âm thanh")
        self.hide_button = button("Ẩn ngay (F10)", lambda: self._command("hide"))
        controls.addWidget(self.teleport_button)
        controls.addWidget(self.hide_button)
        controls.addWidget(self.restore_button)
        gl.addLayout(controls)
        gl.addWidget(label("Hai ngón tay lên trán, giữ 0,5 giây để dịch chuyển.", "muted", True))
        left.addWidget(gesture_card)
        self.warning = label("", "muted", True)
        self.warning.setStyleSheet("color: #a13d21;")
        left.addWidget(self.warning)
        body.addLayout(left, 1)
        self.tabs = QTabWidget()
        self.tabs.setFixedWidth(360)
        self.tabs.setUsesScrollButtons(False)

        def add_tab(caption, frame):
            page = QWidget()
            page.setObjectName("settingsPage")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(16, 18, 16, 18)
            # The selected tab already names the section.
            frame.layout().itemAt(0).widget().hide()
            layout.addWidget(frame)
            layout.addStretch()
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, caption)
        camera_card, cl = card("Camera")
        form = QFormLayout()
        form.setSpacing(10)
        self.camera_combo = QComboBox()
        self.camera_combo.setToolTip("Thử số khác nếu không mở được camera")
        for index in range(10):
            self.camera_combo.addItem(f"Camera {index}", index)
        self.camera_combo.setCurrentIndex(min(self.settings.camera_index, 9))
        self.camera_combo.currentIndexChanged.connect(lambda i: self._change(camera_index=i))
        form.addRow("Thiết bị", self.camera_combo)
        self.camera_mode = QComboBox()
        self.camera_mode.addItem("Dùng chung (Windows)", "shared")
        self.camera_mode.addItem("Tương thích", "compatibility")
        self.camera_mode.setCurrentIndex(max(0, self.camera_mode.findData(self.settings.camera_mode)))
        self.camera_mode.setToolTip("Dùng chung: giữ camera cho các ứng dụng khác, theo định dạng Windows đang dùng.\nTương thích: có thể chiếm riêng webcam; bấm Tắt camera khi dùng ở ứng dụng khác.")
        self.camera_mode.currentIndexChanged.connect(lambda i: self._camera_mode_changed())
        form.addRow("Chế độ", self.camera_mode)
        self.resolution = QComboBox()
        for w, h in ((640, 480), (1280, 720), (1920, 1080)):
            self.resolution.addItem(f"{w} × {h}", (w, h))
        idx = next((i for i in range(self.resolution.count())
                    if tuple(self.resolution.itemData(i)) == (self.settings.width, self.settings.height)), 1)
        self.resolution.setCurrentIndex(max(0, idx))
        self.resolution.currentIndexChanged.connect(self._resolution_changed)
        form.addRow("Độ phân giải", self.resolution)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(5, 60)
        self.fps_spin.setValue(self.settings.fps)
        self.fps_spin.valueChanged.connect(lambda v: self._change(fps=v))
        form.addRow("FPS", self.fps_spin)
        self._camera_mode_changed()
        cl.addLayout(form)
        self.mirror = QCheckBox("Lật gương")
        self.mirror.setToolTip("Áp dụng cho cả xem trước và hình xuất")
        self.mirror.setChecked(self.settings.mirror)
        self.mirror.toggled.connect(lambda v: self._change(mirror=v))
        cl.addWidget(self.mirror)
        cl.addSpacing(6)
        cl.addWidget(label("Nền trống", "section"))
        self.capture_button = button("Chụp nền trống", lambda: self._command("capture"))
        cl.addWidget(self.capture_button)
        self.auto_background = QCheckBox("Tự chụp khi không có người")
        self.auto_background.setChecked(self.settings.auto_background)
        self.auto_background.toggled.connect(self._auto_background_changed)
        cl.addWidget(self.auto_background)
        self.auto_capture_button = button("Chờ chụp nền mới", lambda: self._command("auto_capture"))
        cl.addWidget(self.auto_capture_button)
        background_hint = ("Rời khung hình 2 giây, giữ camera cố định."
                           if self.settings.auto_background else "Bấm chụp rồi rời khung hình trong 3 giây.")
        self.background_label = label(background_hint, "muted", True)
        cl.addWidget(self.background_label)
        add_tab("Camera", camera_card)
        effect_card, el = card("Hiệu ứng")
        self.enabled = QCheckBox("Bật dịch chuyển")
        self.enabled.setChecked(self.settings.enabled)
        self.enabled.toggled.connect(lambda v: self._change(enabled=v))
        el.addWidget(self.enabled)
        self.quick_disappear = QCheckBox("Biến mất tức thì")
        self.quick_disappear.setChecked(self.settings.quick_disappear)
        self.quick_disappear.toggled.connect(self._quick_changed)
        el.addWidget(self.quick_disappear)
        self.complete_hide = QCheckBox("Ẩn hoàn toàn")
        self.complete_hide.setToolTip("Chỉ hiện ảnh nền đã chụp. Bỏ chọn có thể còn viền người.")
        self.complete_hide.setChecked(self.settings.complete_hide)
        self.complete_hide.toggled.connect(lambda v: self._change(complete_hide=v))
        el.addWidget(self.complete_hide)
        el.addWidget(label("Khi ẩn hoàn toàn, cảnh phòng sẽ đứng yên.", "muted", True))
        ef = QFormLayout()
        self.glow_slider = QSlider(Qt.Orientation.Horizontal)
        self.glow_slider.setRange(0, 150)
        self.glow_slider.setValue(round(self.settings.glow * 100))
        self.glow_slider.setToolTip("Cường độ vệt sáng: 0–150%")
        self.glow_slider.valueChanged.connect(lambda v: self._change(glow=v / 100))
        ef.addRow("Độ sáng", self.glow_slider)
        self.disappear = self._duration(self.settings.disappear_seconds, 0.3, 0.7, "disappear_seconds")
        self.appear = self._duration(self.settings.appear_seconds, 0.2, 1.5, "appear_seconds")
        ef.addRow("Biến mất", self.disappear)
        ef.addRow("Xuất hiện lại", self.appear)
        self.sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity.setRange(0, 100)
        self.sensitivity.setValue(round(self.settings.sensitivity * 100))
        self.sensitivity.setToolTip("Tăng độ nhạy để mở rộng vùng nhận cử chỉ trên trán")
        self.sensitivity.valueChanged.connect(lambda v: self._change(sensitivity=v / 100))
        ef.addRow("Độ nhạy", self.sensitivity)
        self.quality = QComboBox()
        for caption, interval in (("Mượt", 1), ("Cân bằng", 2), ("Tiết kiệm CPU", 3)):
            self.quality.addItem(caption, interval)
        self.quality.setCurrentIndex(self.settings.segmentation_every - 1)
        self.quality.currentIndexChanged.connect(lambda i: self._change(segmentation_every=i + 1))
        ef.addRow("Chất lượng", self.quality)
        el.addLayout(ef)
        self.debug = QCheckBox("Xem điểm nhận diện")
        self.debug.setChecked(self.settings.debug)
        self.debug.toggled.connect(lambda v: self._change(debug=v))
        el.addWidget(self.debug)
        self.disappear.setEnabled(not self.settings.quick_disappear)
        add_tab("Hiệu ứng", effect_card)
        audio_card, al = card("Âm thanh khi xuất hiện")
        self.sound_file_label = label(self._sound_caption(), "muted", True)
        al.addWidget(self.sound_file_label)
        sound_buttons = QHBoxLayout()
        sound_buttons.addWidget(button("Chọn tệp…", self._select_sound))
        sound_buttons.addWidget(button("Mặc định", self._default_sound))
        al.addLayout(sound_buttons)
        self.sound_enabled = QCheckBox("Bật âm thanh")
        self.sound_enabled.setChecked(self.settings.sound_enabled)
        self.sound_enabled.toggled.connect(lambda v: self._change(sound_enabled=v))
        al.addWidget(self.sound_enabled)
        audio_form = QFormLayout()
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(round(self.settings.sound_volume * 100))
        self.volume.valueChanged.connect(lambda v: self._change(sound_volume=v / 100))
        audio_form.addRow("Âm lượng", self.volume)
        self.audio_output = QComboBox()
        self.audio_output.addItem("Mặc định của Windows", -1)
        self.audio_output.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.audio_output.setMinimumContentsLength(14)
        try:
            for device_id, name in self.sound.outputs():
                self.audio_output.addItem(name, device_id)
        except Exception:
            self.audio_output.setToolTip("Chưa đọc được danh sách thiết bị âm thanh. Bạn vẫn có thể thử thiết bị mặc định.")
        device_index = self.audio_output.findData(self.settings.audio_device)
        if device_index < 0:
            self._change(audio_device=-1)
        self.audio_output.setCurrentIndex(max(0, device_index))
        self.audio_output.currentIndexChanged.connect(lambda i: self._change(audio_device=self.audio_output.itemData(i)))
        audio_form.addRow("Thiết bị phát", self.audio_output)
        al.addLayout(audio_form)
        al.addWidget(button("Nghe thử", lambda: self._play_sound(preview=True)))
        al.addWidget(label("Âm thanh phát trên máy. Chia sẻ âm thanh máy nếu muốn người trong cuộc gọi nghe.", "muted", True))
        add_tab("Âm thanh", audio_card)
        vl = QHBoxLayout()
        self.virtual_label = label("Camera ảo đang tắt", "muted", True)
        vl.addWidget(self.virtual_label)
        desktop_card, dl = card("Cài đặt")
        self.startup = QCheckBox("Khởi động cùng Windows")
        self.startup.setToolTip("Chạy ở khay hệ thống, không tự bật camera")
        self.startup.setChecked(startup_enabled())
        self.startup.toggled.connect(self._startup_changed)
        dl.addWidget(self.startup)
        self.close_to_tray = QCheckBox("Thu xuống khay khi đóng cửa sổ")
        self.close_to_tray.setChecked(self.settings.close_to_tray)
        self.close_to_tray.toggled.connect(lambda v: self._change(close_to_tray=v))
        dl.addWidget(self.close_to_tray)
        dl.addWidget(label("Camera vẫn chạy khi thu xuống khay. Bấm Thoát để dừng.", "muted", True))
        dl.addWidget(label(f"Phiên bản {__version__}", "muted"))
        add_tab("Cài đặt", desktop_card)
        body.addWidget(self.tabs)
        root.addLayout(body, 1)
        self.status = label("Sẵn sàng", "muted", True)
        footer = QHBoxLayout()
        footer.addWidget(self.status, 1)
        footer.addLayout(vl)
        root.addLayout(footer)
        self._set_running(False)

    def _duration(self, value, low, high, key):
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(0.05)
        spin.setDecimals(2)
        spin.setSuffix(" giây")
        spin.setValue(value)
        spin.valueChanged.connect(lambda v: self._change(**{key: v}))
        return spin

    def _quick_changed(self, enabled):
        self._change(quick_disappear=enabled)
        self.disappear.setEnabled(not enabled)

    def _play_sound(self, preview=False):
        if self._closing or (not preview and (not self.settings.sound_enabled or self.worker is None)):
            return
        self.sound.play(self.settings.sound_volume, self.settings.audio_device, self.settings.sound_file)

    def _sound_caption(self):
        return (Path(self.settings.sound_file).name if self.settings.sound_file
                else "Goku Instant Transmission · 0,89 giây")

    def _select_sound(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn âm thanh dịch chuyển", "",
                                             "Âm thanh (*.mp3 *.wav *.ogg *.flac)",
                                             options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            self._change(sound_file=path)
            self.sound_file_label.setText(self._sound_caption())

    def _default_sound(self):
        self._change(sound_file="")
        self.sound_file_label.setText(self._sound_caption())

    def _auto_background_changed(self, enabled):
        self._change(auto_background=enabled)
        self.auto_capture_button.setEnabled(enabled and self.worker is not None)

    @property
    def has_tray(self):
        return self.tray is not None and self.tray.isVisible()

    def _setup_tray(self):
        if not self._desktop_mode or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(str(resource_root() / "assets" / "animecam.ico")), self)
        menu = QMenu(self)
        for title, callback in (
            ("Mở AnimeCam FX", self.show_window),
            ("Bật camera và camera ảo", self.start_output),
            ("Dừng camera", self._stop_camera),
            ("Thoát ứng dụng", self.request_quit),
        ):
            action = QAction(title, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason in (
            QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        self.tray.setToolTip("AnimeCam FX • webcam đang tắt")
        self.tray.show()
        QApplication.instance().setQuitOnLastWindowClosed(False)

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _startup_changed(self, enabled):
        try:
            set_startup(enabled)
        except OSError as exc:
            with QSignalBlocker(self.startup):
                self.startup.setChecked(not enabled)
            self._error(f"Không đổi được tùy chọn khởi động cùng Windows: {exc}")

    def _stop_camera(self):
        if self.worker is not None:
            self.worker.stop()
            self.camera_button.setEnabled(False)

    def request_quit(self):
        self._quitting = True
        self.close()

    def apply_launch_request(self, payload):
        request = validated_request(payload)
        if self._closing:
            return
        if request["show"]:
            self.show_window()
        if request["virtual"]:
            self.start_output()
        elif request["camera"] and self.worker is None:
            self._toggle_camera()

    def start_output(self):
        if self._closing:
            return
        if self.worker is None:
            self._toggle_camera()
        if not self.virtual_button.property("active") and not self._virtual_requested:
            self._virtual_requested = True
            self._command("virtual_start")
        self.status.setText("Đang chuẩn bị camera…")

    def _resolution_changed(self, index):
        w, h = self.resolution.itemData(index)
        self._change(width=w, height=h)

    def _camera_mode_changed(self):
        self._change(camera_mode=self.camera_mode.currentData())
        can_configure = self.worker is None and self.settings.camera_mode == "compatibility"
        for widget in (self.resolution, self.fps_spin):
            widget.setEnabled(can_configure)
            widget.setToolTip("Chế độ dùng chung giữ độ phân giải và FPS do Windows chọn." if not can_configure else "")

    def _set_running(self, running):
        self.camera_combo.setEnabled(not running)
        self.camera_mode.setEnabled(not running)
        self.resolution.setEnabled(not running and self.settings.camera_mode == "compatibility")
        self.fps_spin.setEnabled(not running and self.settings.camera_mode == "compatibility")
        self.capture_button.setEnabled(running)
        self.auto_capture_button.setEnabled(running and self.settings.auto_background)
        self.teleport_button.setEnabled(running)
        self.restore_button.setEnabled(running)
        self.hide_button.setEnabled(running)
        self.virtual_button.setEnabled(running)
        self.camera_button.setText("Tắt camera" if running else "Bật camera")
        if not running:
            self.state_label.setText("Camera đang tắt")
        if self.tray is not None:
            self.tray.setToolTip("AnimeCam FX • webcam đang chạy" if running else "AnimeCam FX • webcam đang tắt")

    def _toggle_camera(self):
        if self.worker is not None:
            self.worker.stop()
            self.camera_button.setEnabled(False)
            self.status.setText("Đang dừng và giải phóng camera…")
            return
        self.worker = Pipeline(self.settings, self)
        self.worker.error.connect(self._error)
        self.worker.notice.connect(self.status.setText)
        self.worker.virtual_status.connect(self._virtual_status)
        self.worker.return_sound.connect(self._play_sound)
        self.worker.finished.connect(self._finished)
        self._set_running(True)
        self.status.setText("Đang bật camera…")
        self.worker.start()

    def _command(self, command):
        if self.worker is not None:
            if command == "hide":
                self.enabled.setChecked(True)
                self.complete_hide.setChecked(True)
            elif command == "auto_capture":
                self.auto_background.setChecked(True)
            self.worker.command(command)

    def _toggle_virtual(self):
        active = self.virtual_button.property("active") or False
        self.virtual_button.setEnabled(False)
        self._command("virtual_stop" if active else "virtual_start")

    def _virtual_status(self, active, message):
        self._virtual_requested = False
        self.virtual_button.setProperty("active", active)
        self.virtual_button.setText("Tắt camera ảo" if active else "Bật camera ảo")
        self.virtual_button.setEnabled(self.worker is not None and not self._closing)
        self.virtual_label.setText(message)

    def _error(self, message):
        self._virtual_requested = False
        self.status.setText("Lỗi • " + message)
        self.warning.setText(message)
        # Non-modal: capture errors never block worker shutdown or flood modal dialogs.

    def _finished(self):
        if self.worker is None:
            return
        self.worker.deleteLater()
        self.worker = None
        self._virtual_requested = False
        self._set_running(False)
        self.camera_button.setEnabled(True)
        self.live_label.setText("Camera đang tắt")
        self.metrics.setText("")
        self.video.clear()
        self.output_window.video.clear()
        self.progress.setValue(0)
        self.gesture_label.setText("Đang chờ camera")
        self.background_label.setText("Bật camera để chụp nền mới.")
        if not self._closing:
            self.status.setText("Đã nhả webcam cho ứng dụng khác.")
        if self._closing:
            self.close()

    def _poll(self):
        if self.worker is None:
            return
        packet = self.worker.take_packet()
        if packet is None:
            return
        self.video.set_frame(packet.frame)
        if self.output_window.isVisible():
            self.output_window.video.set_frame(packet.output)
        h, w = packet.frame.shape[:2]
        self.live_label.setText("Camera đang bật")
        self.metrics.setText(f"{packet.fps:.0f} FPS · {w} × {h}")
        self.metrics.setToolTip(f"AI {packet.inference_ms:.0f} ms · Độ trễ {packet.latency_ms:.0f} ms")
        state = {"VISIBLE": "Đang hiển thị", "DISAPPEARING": "Đang biến mất", "HIDDEN": "Đã ẩn", "APPEARING": "Đang xuất hiện"}.get(packet.state, packet.state)
        if packet.state == "HIDDEN" and (self.settings.complete_hide or self.settings.quick_disappear):
            state = "Đã ẩn"
        self.state_label.setText(state)
        self.gesture_label.setText(packet.gesture)
        self.score_label.setText(f"{packet.score * 100:.0f}%")
        self.progress.setValue(round(packet.progress * 100))
        self.background_label.setText(packet.background)
        self.capture_button.setText("Chụp lại nền trống" if packet.background_ready else "Chụp nền trống")
        self.warning.setText(packet.warning)
        if packet.virtual:
            self.virtual_label.setText("Camera ảo đang bật")

    def _help(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Trợ giúp — AnimeCam FX")
        dialog.setText("1. Bật camera, rời khung hình để tự chụp nền.\n\n"
            "2. Đưa hai ngón tay lên trán, giữ 0,5 giây để dịch chuyển. Hạ tay trước khi làm lại.\n\n"
            "F9: dịch chuyển · F10: ẩn ngay · F8: hiện ngay.\n\n"
            "Cuộc gọi: cài OBS Studio, bật camera ảo tại đây rồi chọn OBS Virtual Camera trong cuộc gọi.\n\n"
            "Camera ảo chỉ truyền hình. Muốn chia sẻ tiếng hiệu ứng, bật chia sẻ âm thanh máy.")
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        dialog.button(QMessageBox.StandardButton.Ok).setText("Đã hiểu")
        dialog.exec()

    def closeEvent(self, event):
        if self.has_tray and self.settings.close_to_tray and not self._quitting:
            self.hide()
            self.output_window.hide()
            if not self._tray_hint_shown:
                self.tray.showMessage("AnimeCam FX vẫn đang chạy", "Bấm biểu tượng ở khay hệ thống để mở lại. Chọn Thoát để dừng camera.")
                self._tray_hint_shown = True
            event.ignore()
            return
        if self.worker is not None and self.worker.isRunning():
            self._closing = True
            self.worker.stop()
            self.camera_button.setEnabled(False)
            self.status.setText("Đang đóng…")
            event.ignore()
        else:
            self.sound.close()
            self.output_window.close()
            if self.tray is not None:
                self.tray.hide()
            event.accept()
            if self._desktop_mode:
                QApplication.instance().quit()


def apply_theme(app: QApplication):
    QLocale.setDefault(QLocale("vi_VN"))
    app.setStyle("Fusion")
    font = QFont(FONT_FAMILY, 11)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)
    # Qt class-specific defaults otherwise override the application font for
    # menus and dialogs. The same family also drives QPainter text in VideoView.
    for widget_class in ("QWidget", "QLabel", "QPushButton", "QComboBox", "QAbstractSpinBox",
                         "QMenu", "QMenuBar", "QMessageBox", "QFileDialog", "QTipLabel"):
        app.setFont(font, widget_class)
    QToolTip.setFont(font)
    app.setStyleSheet(STYLE.replace("__ASSETS__", (resource_root() / "assets").as_posix()))
