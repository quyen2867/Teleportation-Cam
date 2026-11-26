from dataclasses import dataclass
from pathlib import Path
import sys


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


@dataclass(frozen=True)
class Settings:
    camera_index: int = 0
    camera_mode: str = "shared"
    width: int = 1280
    height: int = 720
    fps: int = 30
    inference_width: int = 640
    segmentation_every: int = 1
    enabled: bool = True
    complete_hide: bool = True
    quick_disappear: bool = True
    sound_enabled: bool = True
    sound_volume: float = 0.3
    audio_device: int = -1
    sound_file: str = ""
    auto_background: bool = True
    close_to_tray: bool = True
    glow: float = 0.7
    disappear_seconds: float = 0.5
    appear_seconds: float = 0.35
    sensitivity: float = 0.5
    mirror: bool = True
    debug: bool = False

    def __post_init__(self):
        if self.camera_mode not in ("shared", "compatibility"):
            raise ValueError("Chế độ camera không hợp lệ")
        if self.width < 160 or self.height < 120 or not 5 <= self.fps <= 60:
            raise ValueError("Độ phân giải hoặc FPS của camera không hợp lệ")
        if not 0.3 <= self.disappear_seconds <= 0.7:
            raise ValueError("Thời gian biến mất phải từ 0,3 đến 0,7 giây")
        if not 0.2 <= self.appear_seconds <= 1.5:
            raise ValueError("Thời gian xuất hiện phải từ 0,2 đến 1,5 giây")
        if not 0 <= self.sensitivity <= 1 or not 0 <= self.glow <= 1.5:
            raise ValueError("Thông số hiệu ứng không hợp lệ")
        if self.segmentation_every not in (1, 2, 3):
            raise ValueError("Tần suất tách người không hợp lệ")
        if not 0 <= self.sound_volume <= 1 or self.audio_device < -1:
            raise ValueError("Âm lượng hoặc thiết bị phát âm thanh không hợp lệ")
