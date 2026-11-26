"""Small ctypes adapter for Windows Frame Server read-only capture."""
import ctypes
from pathlib import Path
import sys

import cv2
import numpy as np

from animecam.config import resource_root


def library_path():
    if getattr(sys, "frozen", False):
        return resource_root() / "native" / "shared_camera.dll"
    return Path(__file__).resolve().parents[1] / "artifacts" / "native" / "shared_camera.dll"


class SharedCamera:
    """Open, poll and close on the same worker thread (COM apartment owner)."""

    def __init__(self, index):
        self.index = index
        self.handle = ctypes.c_void_p()
        self.buffer = None
        self.sequence = 0
        self.dll = None

    @staticmethod
    def _check(result):
        if result < 0:
            raise RuntimeError(
                f"Không đọc được camera dùng chung (0x{result & 0xffffffff:08X}). "
                "Hãy thử camera khác hoặc chế độ Tương thích."
            )

    def open(self):
        path = library_path()
        if not path.is_file():
            raise RuntimeError("Thiếu thành phần camera dùng chung. Hãy cài lại ứng dụng.")
        self.dll = ctypes.CDLL(str(path))
        self.dll.ac_open.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        self.dll.ac_open.restype = ctypes.c_int32
        self.dll.ac_frame.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint64),
        ]
        self.dll.ac_frame.restype = ctypes.c_int32
        self.dll.ac_close.argtypes = [ctypes.c_void_p]
        self.dll.ac_close.restype = None
        self._check(self.dll.ac_open(self.index, ctypes.byref(self.handle)))

    def read(self, timeout=200):
        width, height, sequence = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint64()
        for _ in range(3):
            result = self.dll.ac_frame(
                self.handle, self.sequence, timeout,
                None if self.buffer is None else self.buffer.ctypes.data,
                0 if self.buffer is None else self.buffer.nbytes,
                ctypes.byref(width), ctypes.byref(height), ctypes.byref(sequence),
            )
            self._check(result)
            if result == 1:
                return None
            if result == 2:
                if not 0 < width.value * height.value <= 32 * 1024 * 1024:
                    raise RuntimeError("Kích thước hình camera không hợp lệ.")
                self.buffer = np.empty((height.value, width.value, 4), dtype=np.uint8)
                continue
            self.sequence = sequence.value
            count = height.value * width.value * 4
            bgra = self.buffer.reshape(-1)[:count].reshape(height.value, width.value, 4)
            return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        raise RuntimeError("Camera liên tục đổi kích thước hình. Hãy bật lại camera.")

    def close(self):
        if self.handle.value:
            self.dll.ac_close(self.handle)
            self.handle = ctypes.c_void_p()
