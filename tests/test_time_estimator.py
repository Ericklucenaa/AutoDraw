import pytest

from src.time_estimator import TimeEstimator, drag_delay_for_speed


def _strokes(count, points_each):
    return [[(i, j) for j in range(points_each)] for i in range(count)]


# ---------------- formatting ----------------

@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (-5, "0s"),
        (45, "45s"),
        (59.4, "59s"),
        (60, "1m"),
        (155.0, "2m 35s"),
        (3599, "59m 59s"),
        (3600, "1h"),
        (3660, "1h 01m"),
        (7985, "2h 13m"),
    ],
)
def test_format_time(seconds, expected):
    assert TimeEstimator.format_time(seconds) == expected


# ---------------- estimation ----------------

def test_empty_input_estimates_zero():
    assert TimeEstimator.estimate_seconds([]) == 0.0
    assert TimeEstimator.estimate_seconds([[(1, 1)]]) == 0.0


def test_estimate_grows_with_points():
    small = TimeEstimator.estimate_seconds(_strokes(1, 10))
    large = TimeEstimator.estimate_seconds(_strokes(1, 100))
    assert large > small


def test_estimate_grows_with_stroke_count():
    few = TimeEstimator.estimate_seconds(_strokes(2, 50))
    many = TimeEstimator.estimate_seconds(_strokes(20, 50))
    assert many > few


def test_higher_speed_is_never_slower():
    strokes = _strokes(10, 40)
    times = [TimeEstimator.estimate_seconds(strokes, speed=s) for s in range(1, 101, 9)]
    assert times == sorted(times, reverse=True)


@pytest.mark.parametrize("speed", [-10, 0, 1, 50, 100, 500])
def test_speed_is_clamped(speed):
    assert TimeEstimator.estimate_seconds(_strokes(3, 10), speed=speed) > 0
    assert 0 < drag_delay_for_speed(speed) <= 0.0025


def test_calibration_factor_scales_the_estimate():
    strokes = _strokes(5, 20)
    base = TimeEstimator.estimate_seconds(strokes, calibration_factor=1.0)
    doubled = TimeEstimator.estimate_seconds(strokes, calibration_factor=2.0)
    assert doubled == pytest.approx(base * 2)


def test_calibration_factor_is_clamped():
    strokes = _strokes(5, 20)
    base = TimeEstimator.estimate_seconds(strokes, calibration_factor=1.0)
    assert TimeEstimator.estimate_seconds(strokes, calibration_factor=1e6) == pytest.approx(base * 5)
    assert TimeEstimator.estimate_seconds(strokes, calibration_factor=0) == pytest.approx(base * 0.2)


def test_estimate_accounts_for_input_event_cost():
    """At top speed the requested delay is tiny, so syscall cost must dominate."""
    strokes = _strokes(1, 1000)
    assert TimeEstimator.estimate_seconds(strokes, speed=100) > 1000 * 0.0002


# ---------------- live remaining time ----------------

def test_remaining_time_uses_the_measured_point_rate():
    # 1000 points in 10s => 100 points/s; 400 points left => 4s.
    assert TimeEstimator.remaining_seconds(1000, 1400, 10.0) == pytest.approx(4.0)


def test_remaining_time_reaches_zero_at_the_end():
    assert TimeEstimator.remaining_seconds(500, 500, 5.0) == 0.0


def test_remaining_time_falls_back_before_any_progress():
    assert TimeEstimator.remaining_seconds(0, 500, 0.0, fallback_total=120.0) == 120.0
    assert TimeEstimator.remaining_seconds(0, 500, 30.0, fallback_total=120.0) == pytest.approx(90.0)


def test_remaining_time_is_never_negative():
    assert TimeEstimator.remaining_seconds(0, 500, 999.0, fallback_total=10.0) == 0.0
    assert TimeEstimator.remaining_seconds(600, 500, 5.0) == 0.0


def test_remaining_time_handles_zero_totals():
    assert TimeEstimator.remaining_seconds(0, 0, 1.0) == 0.0


# ---------------- calibration ----------------

def test_calibration_moves_towards_the_observed_ratio():
    # Estimate said 100s (factor 1.0) but it took 200s: the factor must rise.
    updated = TimeEstimator.calibrate(1.0, estimated_seconds=100.0, actual_seconds=200.0)
    assert 1.0 < updated < 2.0


def test_calibration_converges_and_does_not_compound():
    """Feeding back an already-calibrated estimate must leave the factor alone."""
    factor = 1.0
    base_seconds = 100.0
    for _ in range(12):
        estimate = base_seconds * factor
        factor = TimeEstimator.calibrate(factor, estimate, actual_seconds=180.0)
    assert factor == pytest.approx(1.8, abs=0.05)


def test_calibration_is_stable_when_the_estimate_is_right():
    factor = TimeEstimator.calibrate(1.3, estimated_seconds=130.0, actual_seconds=130.0)
    assert factor == pytest.approx(1.3, abs=1e-9)


def test_calibration_stays_in_range():
    assert TimeEstimator.calibrate(1.0, 1.0, 100000.0) <= 5.0
    assert TimeEstimator.calibrate(1.0, 100000.0, 1.0) >= 0.2


def test_calibration_ignores_degenerate_measurements():
    assert TimeEstimator.calibrate(1.4, 0.0, 10.0) == pytest.approx(1.4)
    assert TimeEstimator.calibrate(1.4, 10.0, 0.0) == pytest.approx(1.4)


def test_model_matches_the_measured_real_sessions():
    """
    Guards the cost model against the three recorded drawing runs.

    A SendInput microbenchmark on an idle desktop suggested 0.23ms per move,
    which underestimated real drawing by 2x because the event is serialised
    with the target application's message loop.
    """
    # (strokes, points, actual seconds) observed at speed 100.
    for strokes, points, actual in [(611, 13115, 19.2), (252, 6273, 8.9), (2159, 49870, 68.4)]:
        estimate = TimeEstimator.estimate_seconds(
            [[(0, 0)] * (points // strokes)] * strokes, speed=100, calibration_factor=1.0
        )
        assert estimate == pytest.approx(actual, rel=0.12), (
            f"{strokes} strokes / {points} points: estimated {estimate:.1f}s, measured {actual:.1f}s"
        )
