import math
from typing import List, Tuple


class TimeEstimator:
    """Calculates accurate drawing time estimates based on stroke trajectories and speed settings."""

    @staticmethod
    def estimate_seconds(
        strokes: List[List[Tuple[int, int]]],
        speed: int = 50,
        calibration_factor: float = 1.0
    ) -> float:
        if not strokes:
            return 0.0

        speed_val = max(1, min(100, speed))
        drag_delay = 0.0025 - (speed_val / 100.0) * 0.0024  # seconds per dense step

        in_air_speed_px_per_sec = 2500.0  # estimated Win32 mouse travel speed
        pen_down_time = 0.006  # seconds for positioning + mouse press
        pen_up_time = 0.002    # seconds for mouse release

        curr_x, curr_y = (0, 0)
        total_time = 0.0

        for stroke in strokes:
            if len(stroke) < 2:
                continue

            first_pt = stroke[0]
            dist_air = math.hypot(first_pt[0] - curr_x, first_pt[1] - curr_y)
            t_air = dist_air / in_air_speed_px_per_sec

            point_count = len(stroke)
            t_drag = (point_count - 1) * drag_delay

            stroke_time = t_air + pen_down_time + t_drag + pen_up_time
            total_time += stroke_time

            curr_x, curr_y = stroke[-1]

        final_seconds = total_time * max(0.2, calibration_factor)
        return final_seconds

    @staticmethod
    def format_time(seconds: float) -> str:
        """Formats seconds into human-readable string (e.g., '2m 35s' or '45s')."""
        sec = max(0, int(round(seconds)))
        if sec < 60:
            return f"{sec}s"
        mins = sec // 60
        rem_sec = sec % 60
        if rem_sec == 0:
            return f"{mins}m"
        return f"{mins}m {rem_sec:02d}s"
