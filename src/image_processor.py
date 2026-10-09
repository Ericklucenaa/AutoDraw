from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from src.contour_detector import ContourDetector
from src.logger import get_logger
from src.path_optimizer import PathOptimizer

log = get_logger("processor")

Stroke = List[Tuple[int, int]]


class Cancelled(Exception):
    """Raised internally when a caller cancels processing mid-pipeline."""


def interpolate_stroke(stroke: Stroke, max_step: float = 1.5) -> Stroke:
    """
    Resamples a stroke so consecutive points are at most max_step apart.

    Vectorised with numpy: the original vertices are kept (they are merged into
    the sample positions) and the spacing constraint is met on every segment.
    """
    if len(stroke) < 2:
        return list(stroke)

    pts = np.asarray(stroke, dtype=np.float64)
    deltas = np.diff(pts, axis=0)
    seg_lengths = np.hypot(deltas[:, 0], deltas[:, 1])
    total = float(seg_lengths.sum())
    if total <= 0.0:
        return [(int(round(pts[0][0])), int(round(pts[0][1])))]

    step = max(float(max_step), 1e-3)
    vertex_positions = np.concatenate(([0.0], np.cumsum(seg_lengths)))
    # Sample at a fixed spacing, then fold in the vertices so corners survive.
    samples = np.union1d(np.arange(0.0, total, step), vertex_positions)

    xs = np.rint(np.interp(samples, vertex_positions, pts[:, 0])).astype(np.int64)
    ys = np.rint(np.interp(samples, vertex_positions, pts[:, 1])).astype(np.int64)

    keep = np.ones(len(xs), dtype=bool)
    keep[1:] = (xs[1:] != xs[:-1]) | (ys[1:] != ys[:-1])
    return list(zip(xs[keep].tolist(), ys[keep].tolist()))


class ImageProcessor:
    """Processes images, applies edge detection/binarization, and transforms paths to screen coordinates."""

    @staticmethod
    def process(
        cv_img: np.ndarray,
        target_w: int,
        target_h: int,
        mode: str = "contour",
        aspect_mode: str = "keep_aspect",
        quality_level: str = "media",
        simplify_image: bool = False,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> List[Stroke]:
        """
        Transforms an input image into a list of area-relative stroke vectors
        bounded within (0, 0) to (target_w, target_h).

        Returns an empty list if should_cancel() turns true at any checkpoint.
        """
        if cv_img is None or cv_img.size == 0 or target_w <= 0 or target_h <= 0:
            return []

        def checkpoint() -> None:
            if should_cancel is not None and should_cancel():
                raise Cancelled()

        try:
            return ImageProcessor._run(
                cv_img, target_w, target_h, mode, aspect_mode,
                quality_level, simplify_image, checkpoint, should_cancel,
            )
        except Cancelled:
            log.debug("Processing cancelled by caller")
            return []

    @staticmethod
    def _run(
        cv_img: np.ndarray,
        target_w: int,
        target_h: int,
        mode: str,
        aspect_mode: str,
        quality_level: str,
        simplify_image: bool,
        checkpoint: Callable[[], None],
        should_cancel: Optional[Callable[[], bool]],
    ) -> List[Stroke]:
        gray, offset_x, offset_y = ImageProcessor._fit_to_area(
            cv_img, target_w, target_h, aspect_mode, simplify_image
        )
        checkpoint()

        params = ContourDetector.get_quality_params(quality_level)

        if mode == "bw":
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            edges = cv2.Canny(gray, params.canny_low, params.canny_high)
            raw_strokes = ContourDetector.trace_strokes(edges, quality_level, should_cancel=should_cancel)
            checkpoint()
            raw_strokes += ContourDetector.generate_hatching(binary, quality_level)
        else:
            edges = cv2.Canny(gray, params.canny_low, params.canny_high)
            raw_strokes = ContourDetector.trace_strokes(edges, quality_level, should_cancel=should_cancel)

        checkpoint()

        # Offset into the target coordinate space, then densify for the mouse.
        final_strokes: List[Stroke] = []
        for index, stroke in enumerate(raw_strokes):
            if index % 512 == 0:
                checkpoint()
            clamped = [
                (
                    min(target_w - 1, max(0, offset_x + px)),
                    min(target_h - 1, max(0, offset_y + py)),
                )
                for px, py in stroke
            ]
            dense = interpolate_stroke(clamped, max_step=params.max_step)
            if len(dense) >= 2:
                final_strokes.append(dense)

        checkpoint()
        return PathOptimizer.optimize_paths(final_strokes, should_cancel=should_cancel)

    @staticmethod
    def _fit_to_area(
        cv_img: np.ndarray,
        target_w: int,
        target_h: int,
        aspect_mode: str,
        simplify_image: bool,
    ) -> Tuple[np.ndarray, int, int]:
        """Scales the image into the target area and returns (gray, offset_x, offset_y)."""
        orig_h, orig_w = cv_img.shape[:2]

        if aspect_mode == "stretch":
            resized_w, resized_h = target_w, target_h
            offset_x = offset_y = 0
        elif aspect_mode == "fill":
            scale = max(target_w / float(orig_w), target_h / float(orig_h))
            resized_w = max(1, int(orig_w * scale))
            resized_h = max(1, int(orig_h * scale))
            offset_x = offset_y = 0
        else:  # 'keep_aspect' (default)
            scale = min(target_w / float(orig_w), target_h / float(orig_h))
            resized_w = max(1, int(orig_w * scale))
            resized_h = max(1, int(orig_h * scale))
            offset_x = (target_w - resized_w) // 2
            offset_y = (target_h - resized_h) // 2

        interpolation = cv2.INTER_AREA if resized_w * resized_h < orig_w * orig_h else cv2.INTER_CUBIC
        resized = cv2.resize(cv_img, (resized_w, resized_h), interpolation=interpolation)

        if aspect_mode == "fill":
            crop_x = (resized_w - target_w) // 2
            crop_y = (resized_h - target_h) // 2
            resized = resized[crop_y:crop_y + target_h, crop_x:crop_x + target_w]

        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY) if resized.ndim == 3 else resized

        if simplify_image:
            gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

        return gray, offset_x, offset_y
