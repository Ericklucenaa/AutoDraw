import math
from typing import List, Tuple, Dict, Any
import cv2
import numpy as np

from src.contour_detector import ContourDetector
from src.path_optimizer import PathOptimizer


def interpolate_stroke(stroke: List[Tuple[int, int]], max_step: float = 1.5) -> List[Tuple[int, int]]:
    """
    Interpolates a stroke so that distance between consecutive points is at most max_step.
    """
    if len(stroke) < 2:
        return stroke

    dense: List[Tuple[int, int]] = [stroke[0]]
    for i in range(len(stroke) - 1):
        x1, y1 = stroke[i]
        x2, y2 = stroke[i + 1]
        dist = math.hypot(x2 - x1, y2 - y1)
        if dist > max_step:
            steps = int(math.ceil(dist / max_step))
            for k in range(1, steps + 1):
                nx = int(round(x1 + (x2 - x1) * (k / float(steps))))
                ny = int(round(y1 + (y2 - y1) * (k / float(steps))))
                if (nx, ny) != dense[-1]:
                    dense.append((nx, ny))
        else:
            if stroke[i + 1] != dense[-1]:
                dense.append(stroke[i + 1])
    return dense


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
        simplify_image: bool = False
    ) -> List[List[Tuple[int, int]]]:
        """
        Transforms an input image into a list of screen-relative stroke vectors (dx, dy)
        bounded within (0, 0) to (target_w, target_h).
        """
        if cv_img is None or cv_img.size == 0 or target_w <= 0 or target_h <= 0:
            return []

        orig_h, orig_w = cv_img.shape[:2]

        # 1. Determine scaling and offset based on aspect ratio mode
        if aspect_mode == "stretch":
            rw, rh = target_w, target_h
            ox, oy = 0, 0
        elif aspect_mode == "fill":
            scale = max(target_w / float(orig_w), target_h / float(orig_h))
            rw = max(1, int(orig_w * scale))
            rh = max(1, int(orig_h * scale))
            ox = (rw - target_w) // 2
            oy = (rh - target_h) // 2
        else:  # 'keep_aspect' (default)
            scale = min(target_w / float(orig_w), target_h / float(orig_h))
            rw = max(1, int(orig_w * scale))
            rh = max(1, int(orig_h * scale))
            ox = (target_w - rw) // 2
            oy = (target_h - rh) // 2

        # Resize image
        resized = cv2.resize(cv_img, (rw, rh), interpolation=cv2.INTER_AREA)

        if aspect_mode == "fill":
            resized = resized[oy:oy + target_h, ox:ox + target_w]
            ox, oy = 0, 0
            rw, rh = resized.shape[1], resized.shape[0]

        # 2. Image simplification / noise reduction if requested
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        if simplify_image:
            gray = cv2.bilateralFilter(gray, d=7, sigmaColor=50, sigmaSpace=50)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

        # 3. Contour detection parameters based on quality level ('baixa', 'media', 'alta')
        canny_low, canny_high, _, _, max_step = ContourDetector.get_quality_params(quality_level)
        raw_strokes: List[List[Tuple[int, int]]] = []

        if mode == "contour":
            edges = cv2.Canny(gray, canny_low, canny_high)
            
            # Tiny dilation for medium/low to connect broken lines
            if quality_level != "alta":
                kernel = np.ones((2, 2), np.uint8)
                edges = cv2.dilate(edges, kernel, iterations=1)

            raw_strokes = ContourDetector.extract_contours(edges, quality_level=quality_level)

        else:  # B&W Mode
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            outline_edges = cv2.Canny(gray, canny_low, canny_high)
            outlines = ContourDetector.extract_contours(outline_edges, quality_level=quality_level)
            hatching = ContourDetector.generate_hatching(binary, quality_level=quality_level)
            raw_strokes = outlines + hatching

        # 4. Offset strokes into target coordinate space and interpolate densely
        final_strokes: List[List[Tuple[int, int]]] = []
        for stroke in raw_strokes:
            offset_stroke = []
            for (px, py) in stroke:
                sx = ox + px
                sy = oy + py
                sx = max(0, min(target_w - 1, sx))
                sy = max(0, min(target_h - 1, sy))
                offset_stroke.append((sx, sy))

            dense_stroke = interpolate_stroke(offset_stroke, max_step=max_step)
            if len(dense_stroke) >= 2:
                final_strokes.append(dense_stroke)

        # 5. Optimize stroke execution order (TSP nearest-neighbor)
        optimized_strokes = PathOptimizer.optimize_paths(final_strokes)
        return optimized_strokes
