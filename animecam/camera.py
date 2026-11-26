"""Webcam reader with a single replaceable frame, never an unbounded queue."""
import os
import threading
import time

import cv2

from animecam.config import Settings


class Camera:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._capture = None
        self._thread = None
        self._condition = threading.Condition()
        self._stop = threading.Event()
        self._latest = None
        self._sequence = 0
        self.error = ""
        self.backend = ""

    def open(self):
        if os.name == "nt" and self.settings.camera_mode == "shared":
            self.backend = "Windows dùng chung"
            self._thread = threading.Thread(target=self._read_shared, name="shared-webcam-reader", daemon=True)
            self._thread.start()
            # Wait for a real first frame. A successful handle alone does not
            # prove this driver supports shared streaming.
            first = self.next_frame(0, timeout=12)
            if first is None:
                self.close()
                raise RuntimeError("Camera dùng chung chưa truyền hình. Hãy thử chế độ Tương thích.")
            return
        # DirectShow avoids the slow MSMF mode negotiation common on Windows.
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF] if os.name == "nt" else [cv2.CAP_ANY]
        for backend in backends:
            cap = cv2.VideoCapture(self.settings.camera_index, backend)
            if cap.isOpened():
                self._capture = cap
                break
            cap.release()
        if self._capture is None:
            raise RuntimeError("Không mở được webcam. Hãy kiểm tra số camera, quyền truy cập camera trong Windows và ứng dụng khác đang dùng webcam.")
        cap = self._capture
        self.backend = "Tương thích (DirectShow)" if backend == cv2.CAP_DSHOW else "Tương thích"
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        cap.set(cv2.CAP_PROP_FPS, self.settings.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._thread = threading.Thread(target=self._read, name="webcam-reader", daemon=True)
        self._thread.start()

    def _publish(self, frame):
        with self._condition:
            self._sequence += 1
            self._latest = (self._sequence, time.monotonic(), frame)
            self._condition.notify_all()

    def _read_shared(self):
        from animecam.shared_camera import SharedCamera

        camera = SharedCamera(self.settings.camera_index)
        try:
            camera.open()
            last_frame = time.monotonic()
            while not self._stop.is_set():
                frame = camera.read()
                if frame is not None:
                    self._publish(frame)
                    last_frame = time.monotonic()
                elif time.monotonic() - last_frame > 6:
                    raise RuntimeError("Camera dùng chung không truyền hình. Hãy thử chế độ Tương thích.")
        except Exception as exc:
            self.error = str(exc)
        finally:
            camera.close()
            with self._condition:
                self._condition.notify_all()

    def _read(self):
        failures = 0
        try:
            while not self._stop.is_set():
                ok, frame = self._capture.read()
                if not ok:
                    failures += 1
                    if failures >= 10:
                        raise RuntimeError("Webcam đã mất kết nối hoặc không còn truyền hình.")
                    self._stop.wait(0.05)
                    continue
                failures = 0
                self._publish(frame)
        except Exception as exc:
            self.error = str(exc)
        finally:
            self._capture.release()
            with self._condition:
                self._condition.notify_all()

    def next_frame(self, after: int, timeout: float = 0.2):
        with self._condition:
            self._condition.wait_for(
                lambda: self._sequence > after or bool(self.error) or self._stop.is_set(), timeout
            )
            if self.error:
                raise RuntimeError(self.error)
            if self._latest is not None and self._sequence > after:
                return self._latest
        return None

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                # Keep ownership in the reader; never release concurrently with read().
                raise RuntimeError("Trình điều khiển camera bị kẹt khi đọc hình. Hãy đóng ứng dụng hoặc kết nối lại camera.")
        elif self._capture is not None:
            self._capture.release()
