"""Tests for the pure geometry pipeline: tracing, interpolation and ordering."""
import math

import cv2
import numpy as np
import pytest

from src.contour_detector import ContourDetector
from src.image_processor import ImageProcessor, interpolate_stroke
from src.path_optimizer import PathOptimizer


# ---------------- quality parameters ----------------

@pytest.mark.parametrize("level", ["baixa", "media", "alta", "ALTA", "", None, "unknown"])
def test_quality_params_always_usable(level):
    params = ContourDetector.get_quality_params(level)
    assert params.canny_low < params.canny_high
    assert params.epsilon_px > 0 and params.max_step > 0
    assert params.min_points >= 2 and params.hatch_step >= 1


def test_quality_levels_are_ordered_by_detail():
    low = ContourDetector.get_quality_params("baixa")
    medium = ContourDetector.get_quality_params("media")
    high = ContourDetector.get_quality_params("alta")

    # Lower Canny thresholds and tighter simplification mean more detail.
    assert high.canny_low < medium.canny_low < low.canny_low
    assert high.epsilon_px < medium.epsilon_px < low.epsilon_px
    assert high.max_step < medium.max_step < low.max_step


# ---------------- stroke tracing ----------------

@pytest.fixture
def edge_map(sample_bgr):
    gray = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, 40, 120)


def test_tracer_visits_every_edge_pixel_once(edge_map):
    strokes = ContourDetector.trace_strokes(edge_map, "alta", epsilon_override=0.0)
    points = [point for stroke in strokes for point in stroke]
    assert len(points) == len(set(points)), "an edge pixel was emitted more than once"


def test_tracer_emits_fewer_points_than_find_contours(edge_map):
    """findContours walks a thin edge out and back; the tracer should not."""
    traced = sum(len(s) for s in ContourDetector.trace_strokes(edge_map, "alta", epsilon_override=0.0))
    contours, _ = cv2.findContours(edge_map, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    boundary = sum(len(c) for c in contours)
    assert traced < boundary


def test_traced_points_lie_on_the_edge_map(edge_map):
    strokes = ContourDetector.trace_strokes(edge_map, "alta", epsilon_override=0.0)
    for stroke in strokes:
        for x, y in stroke:
            assert edge_map[y, x] > 128


def test_tracer_handles_empty_and_degenerate_input():
    assert ContourDetector.trace_strokes(None) == []
    assert ContourDetector.trace_strokes(np.zeros((0, 0), np.uint8)) == []
    assert ContourDetector.trace_strokes(np.zeros((50, 50), np.uint8)) == []


def test_tracer_handles_edges_touching_every_border():
    full = np.full((40, 40), 255, np.uint8)
    strokes = ContourDetector.trace_strokes(full, "alta", epsilon_override=0.0)
    assert strokes
    for stroke in strokes:
        for x, y in stroke:
            assert 0 <= x < 40 and 0 <= y < 40


def test_tracer_follows_a_straight_line_as_one_stroke():
    canvas = np.zeros((40, 100), np.uint8)
    canvas[20, 10:90] = 255
    strokes = ContourDetector.trace_strokes(canvas, "alta", epsilon_override=0.0)
    assert len(strokes) == 1
    assert len(strokes[0]) == 80


def test_tracer_is_cancellable(edge_map):
    assert ContourDetector.trace_strokes(edge_map, "alta", should_cancel=lambda: True) == []


# ---------------- hatching ----------------

def _reference_hatching(binary, step):
    """The original per-pixel scanline implementation, kept as an oracle."""
    height, width = binary.shape[:2]
    out = []
    for y in range(0, height, step):
        row = binary[y, :]
        in_shape, start_x = False, 0
        for x in range(width):
            if row[x] > 128 and not in_shape:
                in_shape, start_x = True, x
            elif row[x] <= 128 and in_shape:
                in_shape = False
                if (x - start_x) >= 3:
                    out.append([(start_x, y), (x, y)])
        if in_shape and (width - start_x) >= 3:
            out.append([(start_x, y), (width - 1, y)])
    return out


@pytest.mark.parametrize("level, step", [("baixa", 12), ("media", 7), ("alta", 4)])
def test_hatching_matches_the_reference_scan(level, step):
    rng = np.random.default_rng(11)
    blob = (cv2.GaussianBlur(rng.integers(0, 255, (90, 120), dtype=np.uint8), (9, 9), 0) > 127)
    binary = blob.astype(np.uint8) * 255

    produced = ContourDetector.generate_hatching(binary, level)
    expected = _reference_hatching(binary, step)

    assert len(produced) == len(expected)
    for got, want in zip(produced, expected):
        assert got[0] == want[0]
        assert abs(got[1][0] - want[1][0]) <= 1  # reference used an exclusive end
        assert got[0][1] == want[0][1]


def test_hatching_stays_inside_the_image():
    binary = np.full((30, 25), 255, np.uint8)
    for segment in ContourDetector.generate_hatching(binary, "alta"):
        for x, y in segment:
            assert 0 <= x < 25 and 0 <= y < 30


def test_hatching_handles_empty_input():
    assert ContourDetector.generate_hatching(None) == []
    assert ContourDetector.generate_hatching(np.zeros((20, 20), np.uint8)) == []


# ---------------- interpolation ----------------

@pytest.mark.parametrize("max_step", [0.9, 1.4, 2.2])
@pytest.mark.parametrize(
    "stroke",
    [
        [(0, 0), (10, 0)],
        [(0, 0), (100, 100), (100, 0)],
        [(0, 0), (0, 1)],
        [(0, 0), (200, 7), (10, 180)],
        [(5, 5), (5, 5)],
    ],
)
def test_interpolation_respects_spacing_and_endpoints(stroke, max_step):
    dense = interpolate_stroke(stroke, max_step)

    assert dense[0] == stroke[0]
    assert dense[-1] == stroke[-1]
    # Rounding to integers can stretch a step slightly past the target.
    gaps = [math.dist(dense[i], dense[i + 1]) for i in range(len(dense) - 1)]
    assert all(gap <= max_step + 1.5 for gap in gaps)
    assert all(dense[i] != dense[i + 1] for i in range(len(dense) - 1))


def test_interpolation_preserves_corners():
    assert (100, 100) in interpolate_stroke([(0, 0), (100, 100), (100, 0)], 1.4)


def test_interpolation_passes_through_short_strokes():
    assert interpolate_stroke([], 1.0) == []
    assert interpolate_stroke([(4, 7)], 1.0) == [(4, 7)]


def test_interpolation_densifies_long_segments():
    dense = interpolate_stroke([(0, 0), (100, 0)], 1.0)
    assert len(dense) >= 100


# ---------------- path ordering ----------------

def _nearest_endpoint_distance(strokes, cursor):
    return min(
        min(math.dist(s[0], cursor), math.dist(s[-1], cursor))
        for s in strokes
    )


def test_optimizer_picks_the_nearest_endpoint_at_every_step():
    rng = np.random.default_rng(5)
    strokes = [
        [tuple(rng.integers(-200, 400, 2).tolist()) for _ in range(3)]
        for _ in range(40)
    ]
    ordered = PathOptimizer.optimize_paths(strokes)

    remaining = list(strokes)
    cursor = (0, 0)
    for picked in ordered:
        expected = _nearest_endpoint_distance(remaining, cursor)
        assert math.isclose(math.dist(picked[0], cursor), expected, abs_tol=1e-9)

        # Drop exactly one matching stroke, so duplicates are still accounted for.
        match = next(
            index for index, s in enumerate(remaining)
            if list(s) == list(picked) or list(s)[::-1] == list(picked)
        )
        remaining.pop(match)
        cursor = picked[-1]

    assert len(ordered) == len(strokes)
    assert remaining == []


def test_optimizer_reduces_travel_against_input_order():
    rng = np.random.default_rng(9)
    strokes = [
        [tuple(rng.integers(0, 800, 2).tolist()), tuple(rng.integers(0, 800, 2).tolist())]
        for _ in range(120)
    ]
    before = PathOptimizer.travel_distance(strokes)
    after = PathOptimizer.travel_distance(PathOptimizer.optimize_paths(strokes))
    assert after < before * 0.5


def test_optimizer_reverses_a_stroke_when_its_end_is_closer():
    ordered = PathOptimizer.optimize_paths([[(100, 0), (50, 0), (5, 0)]])
    assert ordered[0][0] == (5, 0)


def test_optimizer_drops_degenerate_strokes():
    ordered = PathOptimizer.optimize_paths([[(1, 1)], [], [(0, 0), (2, 2)]])
    assert ordered == [[(0, 0), (2, 2)]]


def test_optimizer_handles_empty_input_and_cancellation():
    assert PathOptimizer.optimize_paths([]) == []
    assert PathOptimizer.optimize_paths([[(0, 0), (1, 1)]], should_cancel=lambda: True) == []


def test_optimizer_handles_negative_coordinates():
    ordered = PathOptimizer.optimize_paths([[(-500, -500), (-490, -490)], [(0, 0), (3, 3)]])
    assert len(ordered) == 2
    assert ordered[0][0] == (0, 0)  # closest to the (0, 0) start


def test_optimizer_keeps_all_strokes_when_clustered_in_one_cell():
    strokes = [[(i % 4, i % 3), (i % 4 + 1, i % 3 + 1)] for i in range(200)]
    assert len(PathOptimizer.optimize_paths(strokes)) == 200


# ---------------- full pipeline ----------------

@pytest.mark.parametrize("mode", ["contour", "bw"])
@pytest.mark.parametrize("aspect_mode", ["keep_aspect", "fill", "stretch"])
def test_pipeline_output_stays_inside_the_target_area(sample_bgr, mode, aspect_mode):
    strokes = ImageProcessor.process(
        sample_bgr, 320, 240, mode=mode, aspect_mode=aspect_mode, quality_level="media"
    )
    assert strokes
    for stroke in strokes:
        assert len(stroke) >= 2
        for x, y in stroke:
            assert 0 <= x < 320 and 0 <= y < 240


def test_higher_quality_produces_more_detail(sample_bgr):
    low = ImageProcessor.process(sample_bgr, 300, 300, quality_level="baixa")
    high = ImageProcessor.process(sample_bgr, 300, 300, quality_level="alta")
    assert sum(len(s) for s in high) >= sum(len(s) for s in low)


def test_bw_mode_adds_fill_strokes(sample_bgr):
    contour = ImageProcessor.process(sample_bgr, 300, 300, mode="contour", quality_level="media")
    bw = ImageProcessor.process(sample_bgr, 300, 300, mode="bw", quality_level="media")
    assert len(bw) > len(contour)


def test_pipeline_rejects_invalid_inputs(sample_bgr):
    assert ImageProcessor.process(None, 100, 100) == []
    assert ImageProcessor.process(np.zeros((0, 0, 3), np.uint8), 100, 100) == []
    assert ImageProcessor.process(sample_bgr, 0, 100) == []
    assert ImageProcessor.process(sample_bgr, 100, -5) == []


def test_pipeline_is_cancellable(sample_bgr):
    assert ImageProcessor.process(sample_bgr, 400, 400, should_cancel=lambda: True) == []


def test_pipeline_handles_tiny_targets(sample_bgr):
    for stroke in ImageProcessor.process(sample_bgr, 3, 3, quality_level="baixa"):
        for x, y in stroke:
            assert 0 <= x < 3 and 0 <= y < 3


def test_simplification_option_runs(sample_bgr):
    strokes = ImageProcessor.process(
        sample_bgr, 300, 300, quality_level="media", simplify_image=True
    )
    assert isinstance(strokes, list)
