import math
from typing import List, Tuple


class PathOptimizer:
    """Optimizes stroke execution order to minimize travel distance between strokes."""

    @staticmethod
    def optimize_paths(
        strokes: List[List[Tuple[int, int]]]
    ) -> List[List[Tuple[int, int]]]:
        """
        Orders strokes using a greedy nearest-neighbor algorithm.
        Reverses individual strokes when the end point is closer to current cursor.
        """
        if not strokes:
            return []

        remaining = strokes.copy()
        optimized: List[List[Tuple[int, int]]] = []

        # Start with the stroke closest to top-left (0,0)
        curr_pos = (0, 0)

        while remaining:
            best_idx = 0
            best_dist = float("inf")
            reverse_stroke = False

            for i, stroke in enumerate(remaining):
                start_pt = stroke[0]
                end_pt = stroke[-1]

                d_start = math.hypot(start_pt[0] - curr_pos[0], start_pt[1] - curr_pos[1])
                d_end = math.hypot(end_pt[0] - curr_pos[0], end_pt[1] - curr_pos[1])

                if d_start < best_dist:
                    best_dist = d_start
                    best_idx = i
                    reverse_stroke = False

                if d_end < best_dist:
                    best_dist = d_end
                    best_idx = i
                    reverse_stroke = True

            chosen = remaining.pop(best_idx)
            if reverse_stroke:
                chosen = list(reversed(chosen))

            optimized.append(chosen)
            curr_pos = chosen[-1]

        return optimized
