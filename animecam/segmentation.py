import cv2
import numpy as np


class MaskSmoother:
    def __init__(self):
        self.previous = None

    def reset(self):
        self.previous = None

    def apply(self, confidence, size):
        confidence = np.clip(confidence, 0, 1).astype(np.float32)
        # Temporal filtering is applied at model resolution. Fast-changing pixels
        # favor the newest mask, avoiding a persistent trail behind moving limbs.
        if self.previous is not None and self.previous.shape == confidence.shape:
            change = np.abs(confidence - self.previous)
            weight = np.where(change > 0.25, 0.90, 0.65)
            confidence = (weight * confidence + (1 - weight) * self.previous).astype(np.float32)
        self.previous = confidence.copy()
        alpha = np.clip((confidence - 0.15) / 0.65, 0, 1)
        # A small expansion covers hair and uncertain silhouette edges.
        alpha = cv2.dilate(alpha, np.ones((3, 3), np.uint8))
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0.8)
        return cv2.resize(alpha, size, interpolation=cv2.INTER_LINEAR)


class Segmenter:
    def __init__(self, path):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        self.mp = mp
        self.task = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=python.BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            output_category_mask=False, output_confidence_masks=True,
        ))
        self.smoother = MaskSmoother()

    def process(self, rgb, timestamp_ms, output_size):
        # Landscape selfie model has one person confidence channel (not background).
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self.task.segment_for_video(image, timestamp_ms)
        confidence = result.confidence_masks[0].numpy_view().copy()
        return self.smoother.apply(confidence, output_size)

    def close(self):
        self.task.close()
