"""Real BGR frame output to the installed virtual-camera backend."""
import numpy as np


class VirtualCamera:
    def __init__(self, factory=None):
        self._camera = None
        self._factory = factory
        self.frames_sent = 0
        self.size = None

    @property
    def active(self):
        return self._camera is not None

    def start(self, width, height, fps, backend="obs"):
        import pyvirtualcam
        self.stop()
        try:
            factory = self._factory or pyvirtualcam.Camera
            self._camera = factory(width=width, height=height, fps=fps,
                                   fmt=pyvirtualcam.PixelFormat.BGR, backend=backend)
            self.size = (width, height)
            self.frames_sent = 0
            return self._camera.device
        except Exception as exc:
            self._camera, self.size = None, None
            raise RuntimeError(
                "Không bật được camera ảo. Hãy cài OBS Studio kèm camera ảo, "
                "tắt camera ảo trong OBS rồi thử lại. Nếu thiếu trình điều khiển, chạy tệp "
                "data/obs-plugins/win-dshow/virtualcam-install.bat trong thư mục OBS bằng quyền quản trị. "
                f"Chi tiết kỹ thuật: {exc}"
            ) from exc

    def send(self, bgr):
        if self._camera is None:
            raise RuntimeError("Camera ảo chưa được bật")
        if bgr.dtype != np.uint8 or bgr.shape != (self.size[1], self.size[0], 3):
            raise ValueError("Camera ảo cần hình BGR uint8 đúng kích thước đầu ra")
        self._camera.send(np.ascontiguousarray(bgr))
        self.frames_sent += 1

    def stop(self):
        camera, self._camera = self._camera, None
        self.size = None
        if camera is not None:
            camera.close()
