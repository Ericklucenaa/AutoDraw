from typing import List, Tuple
import cv2
import numpy as np


class ContourDetector:
    """Detects contours and generates vector paths from processed images."""

    @staticmethod
    def get_quality_params(quality_level: str) -> Tuple[int, int, float, int, float]:
        """
        Returns (canny_low, canny_high, epsilon_factor, min_length, max_step)
        for quality levels 'baixa', 'media', 'alta'.
        """
        lvl = quality_level.lower()
        if lvl == "baixa":
            return (90, 190, 2.4, 10, 2.2)
        elif lvl == "alta":
            return (15, 65, 0.4, 2, 0.9)
        else:  # 'media' (default)
            return (40, 120, 1.1, 5, 1.4)

    @staticmethod
    def extract_contours(
        binary_image: np.ndarray,
        quality_level: str = "media",
        epsilon_override: float = None
    ) -> List[List[Tuple[int, int]]]:
        """
        Extracts stroke paths from a binary (0/255) edge image.
        """
        if binary_image is None or binary_image.size == 0:
            return []

        canny_low, canny_high, epsilon_factor, min_length, _ = ContourDetector.get_quality_params(quality_level)
        if epsilon_override is not None:
            epsilon_factor = epsilon_override

        contours, _ = cv2.findContours(
            binary_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE
        )

        strokes: List[List[Tuple[int, int]]] = []

        for cnt in contours:
            if len(cnt) < min_length:
                continue

            # Simplify curve using Ramer-Douglas-Peucker
            approx = cv2.approxPolyDP(cnt, epsilon_factor, closed=False)
            
            # Convert contours to list of (x, y) points
            points = [(int(pt[0][0]), int(pt[0][1])) for pt in approx]

            if len(points) >= 2:
                strokes.append(points)

        return strokes

    @staticmethod
    def generate_hatching(
        binary_filled: np.ndarray,
        quality_level: str = "media"
    ) -> List[List[Tuple[int, int]]]:
        """
        Generates scanline hatching for black/filled regions in B&W mode.
        """
        if binary_filled is None or binary_filled.size == 0:
            return []

        h, w = binary_filled.shape[:2]
        lvl = quality_level.lower()
        if lvl == "baixa":
            step = 12
        elif lvl == "alta":
            step = 4
        else:
            step = 7

        hatch_strokes: List[List[Tuple[int, int]]] = []

        for y in range(0, h, step):
            row = binary_filled[y, :]
            in_shape = False
            start_x = 0
            for x in range(w):
                if row[x] > 128 and not in_shape:
                    in_shape = True
                    start_x = x
                elif row[x] <= 128 and in_shape:
                    in_shape = False
                    if (x - start_x) >= 3:
                        hatch_strokes.append([(start_x, y), (x, y)])
            if in_shape and (w - start_x) >= 3:
                hatch_strokes.append([(start_x, y), (w - 1, y)])

        return hatch_strokes
