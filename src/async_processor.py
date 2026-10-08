from typing import List, Tuple, Optional
import numpy as np
from PySide6.QtCore import QThread, Signal

from src.image_processor import ImageProcessor
from src.time_estimator import TimeEstimator


class ImageProcessorWorker(QThread):
    """
    Asynchronous QThread worker that runs OpenCV image processing and trajectory
    calculation in background without freezing the UI.
    """
    processing_finished = Signal(list, float, int)  # strokes, estimated_seconds, total_points
    processing_error = Signal(str)

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
        parent=None
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

    def run(self) -> None:
        try:
            strokes = ImageProcessor.process(
                cv_img=self.cv_img,
                target_w=self.target_w,
                target_h=self.target_h,
                mode=self.mode,
                aspect_mode=self.aspect_mode,
                quality_level=self.quality_level,
                simplify_image=self.simplify_image
            )

            est_seconds = TimeEstimator.estimate_seconds(
                strokes=strokes,
                speed=self.speed,
                calibration_factor=self.calibration_factor
            )

            total_pts = sum(len(s) for s in strokes)
            self.processing_finished.emit(strokes, est_seconds, total_pts)

        except Exception as e:
            self.processing_error.emit(str(e))
