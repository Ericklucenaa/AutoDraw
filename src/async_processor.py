from typing import List, Tuple

import numpy as np
from PySide6.QtCore import QThread, Signal

from src.image_processor import ImageProcessor
from src.logger import get_logger
from src.time_estimator import TimeEstimator

log = get_logger("async")

Stroke = List[Tuple[int, int]]


class ImageProcessorWorker(QThread):
    """
    Asynchronous QThread worker that runs OpenCV image processing and trajectory
    calculation in background without freezing the UI.
    """
    # strokes, estimated_seconds, total_points, request_id
    processing_finished = Signal(list, float, int, int)
    processing_error = Signal(str, int)
    processing_cancelled = Signal(int)

    def __init__(
        self,
        cv_img: np.ndarray,
        target_w: int,
        target_h: int,
        mode: str = "contour",
        aspect_mode: str = "keep_aspect",
        quality_level: str = "media",
        simplify_image: bool = False,
        speed: int = 50,
        calibration_factor: float = 1.0,
        request_id: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.cv_img = cv_img
        self.target_w = target_w
        self.target_h = target_h
        self.mode = mode
        self.aspect_mode = aspect_mode
        self.quality_level = quality_level
        self.simplify_image = simplify_image
        self.speed = speed
        self.calibration_factor = calibration_factor
        self.request_id = request_id
        self._cancelled = False

    def cancel(self) -> None:
        """
        Asks the worker to stop at its next checkpoint.

        Cooperative cancellation replaces QThread.terminate(), which could kill
        the thread inside an OpenCV call and leave allocator state corrupted.
        """
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            strokes = ImageProcessor.process(
                cv_img=self.cv_img,
                target_w=self.target_w,
                target_h=self.target_h,
                mode=self.mode,
                aspect_mode=self.aspect_mode,
                quality_level=self.quality_level,
                simplify_image=self.simplify_image,
                should_cancel=lambda: self._cancelled,
            )

            if self._cancelled:
                self.processing_cancelled.emit(self.request_id)
                return

            estimated = TimeEstimator.estimate_seconds(
                strokes=strokes,
                speed=self.speed,
                calibration_factor=self.calibration_factor,
            )
            total_points = sum(len(s) for s in strokes)
            log.debug(
                "Processed %s/%s: %d strokes, %d points",
                self.quality_level, self.mode, len(strokes), total_points,
            )
            self.processing_finished.emit(strokes, estimated, total_points, self.request_id)

        except Exception as e:
            log.exception("Image processing failed")
            self.processing_error.emit(str(e), self.request_id)
