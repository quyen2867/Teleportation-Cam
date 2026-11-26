from typing import Protocol
from enum import Enum

import numpy as np

from animecam.config import Settings


class Effect(Protocol):
    """New effects implement this contract and are injected into the pipeline."""
    state: Enum
    def trigger(self, now: float, background_ready: bool, quick_exit: bool = False) -> bool: ...
    def hide(self, background_ready: bool) -> bool: ...
    def restore(self) -> None: ...
    def render(self, frame: np.ndarray, mask: np.ndarray,
               background: np.ndarray | None, now: float, settings: Settings) -> np.ndarray: ...
