from typing import List, Sequence, Tuple

Stroke = List[Tuple[int, int]]

# Bump whenever the cost model below changes: a stored calibration_factor is
# only meaningful for the model it was measured against.
MODEL_VERSION = 2

# Cost of one Win32 input event while a drawing application is consuming it.
# A SendInput microbenchmark on an idle desktop reports ~0.23ms per move, but
# that underestimates real drawing by 2x: the event is serialised with the
# target application's message loop, which is also repainting. Fitted against
# real sessions (611/13115, 252/6273 and 2159/49870 strokes/points at speed
# 100, taking 19.2s, 8.9s and 68.4s), 1.0ms per move lands within 8% on all
# three. calibration_factor absorbs the remaining per-machine difference.
MOVE_EVENT_COST = 0.0010
BUTTON_EVENT_COST = 0.00042

# Settle delays applied by DrawingEngineWorker around each stroke.
PEN_SETTLE_BEFORE_PRESS = 0.004
PEN_SETTLE_AFTER_PRESS = 0.002
PEN_SETTLE_AFTER_RELEASE = 0.002

MIN_CALIBRATION = 0.2
MAX_CALIBRATION = 5.0


def drag_delay_for_speed(speed: int) -> float:
    """Per-point delay requested by the speed slider (1 = slow, 100 = fast)."""
    speed_val = max(1, min(100, int(speed)))
    return 0.0025 - (speed_val / 100.0) * 0.0024


class TimeEstimator:
    """Calculates drawing time estimates from stroke trajectories and speed settings."""

    @staticmethod
    def estimate_seconds(
        strokes: Sequence[Stroke],
        speed: int = 50,
        calibration_factor: float = 1.0,
    ) -> float:
        """
        Estimates total drawing time.

        The model mirrors what DrawingEngineWorker actually does per stroke:
        one positioning move, a press, one move per remaining point, a release,
        plus the fixed settle delays. Travel distance does not appear because
        positioning is a single absolute jump, not a timed glide.
        """
        total_strokes, total_points = _counts(strokes)
        if total_strokes == 0:
            return 0.0

        per_stroke = (
            MOVE_EVENT_COST
            + PEN_SETTLE_BEFORE_PRESS
            + BUTTON_EVENT_COST
            + PEN_SETTLE_AFTER_PRESS
            + BUTTON_EVENT_COST
            + PEN_SETTLE_AFTER_RELEASE
        )
        drag_points = max(0, total_points - total_strokes)
        per_point = MOVE_EVENT_COST + drag_delay_for_speed(speed)

        total = total_strokes * per_stroke + drag_points * per_point
        return total * _clamp_calibration(calibration_factor)

    @staticmethod
    def remaining_seconds(
        points_done: int,
        points_total: int,
        elapsed_seconds: float,
        fallback_total: float = 0.0,
    ) -> float:
        """
        Projects the remaining time from the measured points-per-second rate.

        Strokes vary from 2 to hundreds of points, so extrapolating from the
        number of finished strokes made the countdown jump around; points are
        very nearly uniform in cost.
        """
        if points_total <= 0 or points_done <= 0 or elapsed_seconds <= 0:
            return max(0.0, fallback_total - max(0.0, elapsed_seconds))
        rate = points_done / elapsed_seconds
        if rate <= 0:
            return max(0.0, fallback_total - elapsed_seconds)
        return max(0.0, (points_total - points_done) / rate)

    @staticmethod
    def calibrate(
        current_factor: float,
        estimated_seconds: float,
        actual_seconds: float,
        weight: float = 0.3,
    ) -> float:
        """Blends the observed estimate/actual ratio into the stored factor."""
        if estimated_seconds <= 0 or actual_seconds <= 0:
            return _clamp_calibration(current_factor)
        # The stored factor is already baked into estimated_seconds, so undo it
        # before measuring, otherwise repeated drawings compound the correction.
        base = estimated_seconds / _clamp_calibration(current_factor)
        if base <= 0:
            return _clamp_calibration(current_factor)
        observed = actual_seconds / base
        blended = current_factor * (1.0 - weight) + observed * weight
        return _clamp_calibration(blended)

    @staticmethod
    def format_time(seconds: float) -> str:
        """Formats seconds into human-readable string (e.g., '2m 35s' or '45s')."""
        sec = max(0, int(round(seconds)))
        if sec < 60:
            return f"{sec}s"
        if sec < 3600:
            mins, rem = divmod(sec, 60)
            return f"{mins}m" if rem == 0 else f"{mins}m {rem:02d}s"
        hours, rem = divmod(sec, 3600)
        mins = rem // 60
        return f"{hours}h" if mins == 0 else f"{hours}h {mins:02d}m"


def _counts(strokes: Sequence[Stroke]):
    total_strokes = 0
    total_points = 0
    for stroke in strokes:
        length = len(stroke)
        if length >= 2:
            total_strokes += 1
            total_points += length
    return total_strokes, total_points


def _clamp_calibration(factor: float) -> float:
    try:
        return max(MIN_CALIBRATION, min(MAX_CALIBRATION, float(factor)))
    except (TypeError, ValueError):
        return 1.0
