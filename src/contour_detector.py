from typing import Callable, List, NamedTuple, Optional, Tuple

import cv2
import numpy as np

Stroke = List[Tuple[int, int]]

# The eight neighbour offsets in angular order, so consecutive entries are 45
# degrees apart. Walking them relative to the previous heading keeps traced
# strokes straight instead of zig-zagging between diagonal and orthogonal steps.
_OFFSETS: Tuple[Tuple[int, int], ...] = (
    (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1),
)
# Preference order applied to the heading: straight on, then gentle turns.
_TURN_ORDER: Tuple[int, ...] = (0, 1, -1, 2, -2, 3, -3, 4)

# Border added around the mask so neither the neighbour walk nor the widest
# gap bridge (max_bridge = 3) can index outside the array.
_PAD = 3


class QualityParams(NamedTuple):
    """Tunables derived from the user-facing quality level."""
    canny_low: int
    canny_high: int
    epsilon_px: float   # Ramer-Douglas-Peucker tolerance, in pixels
    min_points: int     # strokes shorter than this are discarded
    max_step: float     # maximum spacing between interpolated points
    hatch_step: int     # scanline spacing for B&W fill
    max_bridge: int     # how far a trace may jump to close a broken edge


class ContourDetector:
    """Traces vector strokes from processed images."""

    @staticmethod
    def get_quality_params(quality_level: str) -> QualityParams:
        """Returns the tunables for the low, medium and high quality levels."""
        lvl = (quality_level or "").lower()
        if lvl == "baixa":
            return QualityParams(90, 190, 2.4, 10, 2.2, 12, 3)
        if lvl == "alta":
            return QualityParams(15, 65, 0.4, 2, 0.9, 4, 2)
        return QualityParams(40, 120, 1.1, 5, 1.4, 7, 2)

    @staticmethod
    def trace_strokes(
        edge_map: np.ndarray,
        quality_level: str = "media",
        epsilon_override: Optional[float] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> List[Stroke]:
        """
        Converts a thin binary edge map into open polylines, visiting every
        edge pixel exactly once.

        cv2.findContours walks the boundary of a region, so on a one-pixel wide
        Canny edge it travels out along the line and back again, emitting about
        1.4x more points than there are edge pixels and making the mouse redraw
        every line twice. Following the edge pixels directly costs one point
        per pixel and draws each line once.
        """
        if edge_map is None or edge_map.size == 0:
            return []

        params = ContourDetector.get_quality_params(quality_level)
        epsilon = params.epsilon_px if epsilon_override is None else epsilon_override

        mask = np.ascontiguousarray(edge_map > 128)
        if not mask.any():
            return []

        height, width = mask.shape[:2]
        # Padding removes every bounds check from the inner walk.
        alive = np.zeros((height + 2 * _PAD, width + 2 * _PAD), dtype=bool)
        alive[_PAD:_PAD + height, _PAD:_PAD + width] = mask

        mask_u8 = mask.astype(np.uint8)
        degree = cv2.filter2D(
            mask_u8, -1, np.ones((3, 3), np.uint8), borderType=cv2.BORDER_CONSTANT
        ) - mask_u8

        ys, xs = np.nonzero(mask)
        deg_values = degree[ys, xs]
        # Line ends first, so an open curve comes out as one stroke; then
        # junctions; then whatever is left, which is closed loops.
        priority = np.where(deg_values == 1, 0, np.where(deg_values >= 3, 1, 2))
        seed_order = np.argsort(priority, kind="stable")

        raw: List[Stroke] = []
        for counter, seed in enumerate(seed_order):
            if should_cancel is not None and counter % 4096 == 0 and should_cancel():
                return []
            py, px = int(ys[seed]) + _PAD, int(xs[seed]) + _PAD
            if not alive[py, px]:
                continue
            raw.append(_walk_from(alive, px, py, params.max_bridge))

        return ContourDetector._simplify(raw, epsilon, params.min_points)

    @staticmethod
    def extract_contours(
        binary_image: np.ndarray,
        quality_level: str = "media",
        epsilon_override: Optional[float] = None,
    ) -> List[Stroke]:
        """Deprecated alias kept for callers written against the old API."""
        return ContourDetector.trace_strokes(binary_image, quality_level, epsilon_override)

    @staticmethod
    def _simplify(raw: List[Stroke], epsilon: float, min_points: int) -> List[Stroke]:
        strokes: List[Stroke] = []
        for points in raw:
            if len(points) < min_points:
                continue
            if epsilon > 0 and len(points) > 2:
                arr = np.asarray(points, dtype=np.int32).reshape(-1, 1, 2)
                approx = cv2.approxPolyDP(arr, epsilon, closed=False)
                simplified = [(int(p[0][0]), int(p[0][1])) for p in approx]
            else:
                simplified = points
            if len(simplified) >= 2:
                strokes.append(simplified)
        return strokes

    @staticmethod
    def generate_hatching(binary_filled: np.ndarray, quality_level: str = "media") -> List[Stroke]:
        """
        Generates scanline hatching for the filled regions used by B&W mode.

        Run boundaries come from a vectorised diff over the sampled rows; the
        previous per-pixel Python scan cost one interpreter iteration per pixel.
        """
        if binary_filled is None or binary_filled.size == 0:
            return []

        step = max(1, ContourDetector.get_quality_params(quality_level).hatch_step)
        rows = binary_filled[::step] > 128
        if not rows.any():
            return []

        # Pad both sides with "off" so a run touching an edge still produces
        # both a rising and a falling transition.
        padded = np.pad(rows, ((0, 0), (1, 1)), mode="constant", constant_values=False)
        transitions = np.diff(padded.astype(np.int8), axis=1)

        start_rows, start_xs = np.nonzero(transitions == 1)
        _, end_xs = np.nonzero(transitions == -1)

        lengths = end_xs - start_xs
        keep = lengths >= 3
        start_rows, start_xs, end_xs = start_rows[keep], start_xs[keep], end_xs[keep]

        max_x = binary_filled.shape[1] - 1
        return [
            [(int(x0), int(row) * step), (int(min(x1 - 1, max_x)), int(row) * step)]
            for row, x0, x1 in zip(start_rows, start_xs, end_xs)
        ]


def _walk_from(alive: np.ndarray, px: int, py: int, max_bridge: int) -> Stroke:
    """Follows an unbroken run of edge pixels from (px, py) in padded coordinates."""
    alive[py, px] = False
    stroke: Stroke = [(px - _PAD, py - _PAD)]
    heading = 0

    while True:
        step = _next_neighbour(alive, px, py, heading)
        if step is None and max_bridge > 1:
            step = _bridge_gap(alive, px, py, heading, max_bridge)
        if step is None:
            break

        dx, dy, heading = step
        px, py = px + dx, py + dy
        alive[py, px] = False
        stroke.append((px - _PAD, py - _PAD))

    return stroke


def _next_neighbour(alive: np.ndarray, px: int, py: int, heading: int):
    """Picks the adjacent live pixel that deviates least from the heading."""
    for turn in _TURN_ORDER:
        direction = (heading + turn) % 8
        dx, dy = _OFFSETS[direction]
        if alive[py + dy, px + dx]:
            return dx, dy, direction
    return None


def _bridge_gap(alive: np.ndarray, px: int, py: int, heading: int, max_bridge: int):
    """
    Jumps a small gap to the nearest live pixel lying roughly ahead.

    This replaces dilating the edge map to reconnect broken lines: dilation
    thickened every edge, which then traced as two parallel strokes.
    """
    hx, hy = _OFFSETS[heading]
    best = None
    best_cost = None

    for radius in range(2, max_bridge + 1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                if not alive[py + dy, px + dx]:
                    continue
                # Only continue forwards, so a trace cannot hop onto a
                # different line running alongside this one.
                if dx * hx + dy * hy <= 0:
                    continue
                cost = dx * dx + dy * dy
                if best_cost is None or cost < best_cost:
                    best_cost = cost
                    best = (dx, dy)
        if best is not None:
            break

    if best is None:
        return None

    dx, dy = best
    direction = min(
        range(8), key=lambda i: (_OFFSETS[i][0] - dx) ** 2 + (_OFFSETS[i][1] - dy) ** 2
    )
    return dx, dy, direction
