"""Real BGR frame output to the installed virtual-camera backend."""
import sys

import numpy as np

SYPHON_SERVER_NAME = "AnimeCam FX"


class VirtualCamera:
    """BGR frame output; macOS uses Syphon, other systems use OBS's driver."""

    def __init__(self, factory=None):
        self._camera = None
        self._factory = factory
        self._syphon = SyphonCamera() if factory is None and sys.platform == "darwin" else None
        self.frames_sent = 0
        self.size = None

    @property
    def active(self):
        return self._syphon.active if self._syphon is not None else self._camera is not None

    def start(self, width, height, fps, backend="obs"):
        if self._syphon is not None:
            device = self._syphon.start(width, height, fps)
            self.size, self.frames_sent = (width, height), 0
            return device
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
        if self._syphon is not None:
            self._syphon.send(bgr)
            self.frames_sent = self._syphon.frames_sent
            return
        if self._camera is None:
            raise RuntimeError("Camera ảo chưa được bật")
        if bgr.dtype != np.uint8 or bgr.shape != (self.size[1], self.size[0], 3):
            raise ValueError("Camera ảo cần hình BGR uint8 đúng kích thước đầu ra")
        self._camera.send(np.ascontiguousarray(bgr))
        self.frames_sent += 1

    def stop(self):
        if self._syphon is not None:
            self._syphon.stop()
            self.size, self.frames_sent = None, 0
            return
        camera, self._camera = self._camera, None
        self.size = None
        if camera is not None:
            camera.close()


class SyphonCamera:
    """Publish BGR frames to macOS apps (OBS) through a Syphon Metal server."""

    def __init__(self, server_factory=None, texture_factory=None, upload=None):
        self._server_factory = server_factory
        self._texture_factory = texture_factory
        self._upload = upload
        self._server = None
        self._texture = None
        self.size = None
        self.frames_sent = 0

    @property
    def active(self):
        return self._server is not None

    def _dependencies(self):
        if self._server_factory is not None:
            return self._server_factory, self._texture_factory, self._upload
        try:
            import syphon
            from syphon.utils.raw import copy_bytes_to_mtl_texture, create_mtl_texture
        except ImportError as exc:
            raise RuntimeError(
                "Chưa cài syphon-python. Chạy: pip install syphon-python"
            ) from exc
        return (lambda: syphon.SyphonMetalServer(SYPHON_SERVER_NAME),
                create_mtl_texture, copy_bytes_to_mtl_texture)

    def start(self, width, height, fps, backend="obs"):
        self.stop()
        server_factory, texture_factory, upload = self._dependencies()
        server = None
        try:
            server = server_factory()
            texture = texture_factory(server.device, width, height)
        except Exception as exc:
            if server is not None:
                try:
                    server.stop()
                except Exception:
                    pass
            raise RuntimeError(
                "Không bật được đầu ra Syphon. Hãy kiểm tra OBS Studio đã cài và thử lại. "
                f"Chi tiết kỹ thuật: {exc}"
            ) from exc
        self._server, self._texture, self._upload = server, texture, upload
        self.size = (width, height)
        self.frames_sent = 0
        return f"{SYPHON_SERVER_NAME} (Syphon)"

    def send(self, bgr):
        if self._server is None:
            raise RuntimeError("Camera ảo chưa được bật")
        if bgr.dtype != np.uint8 or bgr.shape != (self.size[1], self.size[0], 3):
            raise ValueError("Camera ảo cần hình BGR uint8 đúng kích thước đầu ra")
        import cv2
        rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
        self._upload(rgba.tobytes(), self._texture)
        self._server.publish_frame_texture(self._texture)
        self.frames_sent += 1

    def stop(self):
        server, self._server = self._server, None
        self._texture = None
        self.size = None
        if server is not None:
            server.stop()
