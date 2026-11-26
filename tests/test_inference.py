"""Runs real Tasks graphs on a blank frame; no hardware is simulated or claimed."""
import numpy as np
import pytest

from animecam.models import model_paths
from animecam.segmentation import Segmenter
from animecam.tracking import Tracker


@pytest.mark.integration
def test_real_cpu_models_load_and_infer():
    paths = model_paths()
    tracker = Tracker(paths)
    segmenter = None
    try:
        segmenter = Segmenter(paths["selfie_segmenter.tflite"])
        blank = np.zeros((360, 640, 3), np.uint8)
        observation = tracker.process(blank, 1, 0.5)
        assert observation.score is None and not observation.hands
        mask = segmenter.process(np.zeros((144, 256, 3), np.uint8), 1, (640, 360))
        assert mask.shape == (360, 640) and np.isfinite(mask).all()
        assert mask.min() >= 0 and mask.max() <= 1
        # A blank scene must not be classified as an all-person mask.
        assert np.mean(mask > 0.5) < 0.1
        tracker.process(blank, 34, 0.5)
        segmenter.process(np.zeros((144, 256, 3), np.uint8), 34, (640, 360))
    finally:
        tracker.close()
        if segmenter:
            segmenter.close()
