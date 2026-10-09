"""Widget and worker tests. The drawing engine runs against a fake mouse."""
import numpy as np
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtGui import QPixmap

from src.async_processor import ImageProcessorWorker
from src.drawing_engine import DrawingEngineWorker
from src.ui.widgets import ImagePreviewCanvas, RecentImagesBar, cv_to_pixmap


# ---------------- preview canvas ----------------

@pytest.mark.parametrize("shape", [(50, 70, 3), (100, 137, 3), (1, 1, 3), (480, 641, 3), (33, 33, 3)])
def test_cv_to_pixmap_accepts_any_width(qapp, shape):
    """
    A [:, :, ::-1] slice is a reversed-stride view whose memoryview cannot be
    exported, so QImage raised BufferError for every image that was loaded.
    """
    pixmap = cv_to_pixmap(np.full(shape, 128, np.uint8))
    assert pixmap is not None and not pixmap.isNull()
    assert (pixmap.width(), pixmap.height()) == (shape[1], shape[0])


def test_cv_to_pixmap_keeps_channel_order(qapp):
    blue_bgr = np.zeros((4, 4, 3), np.uint8)
    blue_bgr[:, :, 0] = 255
    colour = cv_to_pixmap(blue_bgr).toImage().pixelColor(0, 0)
    assert (colour.red(), colour.green(), colour.blue()) == (0, 0, 255)

    red_bgr = np.zeros((4, 4, 3), np.uint8)
    red_bgr[:, :, 2] = 255
    colour = cv_to_pixmap(red_bgr).toImage().pixelColor(0, 0)
    assert (colour.red(), colour.green(), colour.blue()) == (255, 0, 0)


def test_cv_to_pixmap_accepts_grayscale(qapp):
    assert cv_to_pixmap(np.full((10, 10), 200, np.uint8)) is not None


def test_cv_to_pixmap_rejects_empty(qapp):
    assert cv_to_pixmap(None) is None
    assert cv_to_pixmap(np.zeros((0, 0, 3), np.uint8)) is None


def test_set_image_builds_a_pixmap(qapp):
    canvas = ImagePreviewCanvas()
    canvas.set_image(np.full((60, 83, 3), 100, np.uint8))
    assert canvas._pixmap is not None and not canvas._pixmap.isNull()

    canvas.set_image(None)
    assert canvas._pixmap is None


@pytest.mark.parametrize("mode", ["processed", "original", "area"])
def test_canvas_renders_every_view_mode(qapp, mode):
    canvas = ImagePreviewCanvas()
    canvas.resize(400, 300)
    canvas.set_image(np.full((200, 300, 3), 90, np.uint8))
    canvas.set_vector_paths([[(i, i), (i + 20, i + 5)] for i in range(0, 180, 9)], 300, 200)
    canvas.set_view_mode(mode)

    target = QPixmap(canvas.size())
    canvas.render(target)
    assert not target.isNull()


def test_canvas_renders_without_an_image(qapp):
    canvas = ImagePreviewCanvas()
    canvas.resize(320, 240)
    canvas.render(QPixmap(canvas.size()))

    canvas.set_drag_hover(True)
    canvas.render(QPixmap(canvas.size()))


def test_canvas_survives_a_zero_sized_target_area(qapp):
    canvas = ImagePreviewCanvas()
    canvas.resize(200, 200)
    canvas.set_image(np.full((50, 50, 3), 10, np.uint8))
    canvas.set_vector_paths([[(0, 0), (5, 5)]], 0, 0)
    canvas.render(QPixmap(canvas.size()))


# ---------------- recent images bar ----------------

def test_recent_bar_skips_missing_files(qapp, tmp_path):
    existing = tmp_path / "there.png"
    existing.write_bytes(b"x")

    bar = RecentImagesBar()
    bar.set_recent_files([str(existing), str(tmp_path / "gone.png")])
    # One label plus exactly one pill button.
    assert bar._layout.count() == 2

    bar.set_recent_files([])
    assert bar._layout.count() == 0


def test_recent_bar_emits_the_clicked_path(qapp, tmp_path):
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    for path in (first, second):
        path.write_bytes(b"x")

    bar = RecentImagesBar()
    bar.set_recent_files([str(first), str(second)])
    received = []
    bar.image_selected.connect(received.append)

    bar._layout.itemAt(2).widget().click()
    assert received == [str(second)]


# ---------------- fake mouse ----------------

class FakeMouse:
    """Records what the engine would have done instead of moving the pointer."""

    controller_class = None

    def __init__(self):
        self.moves = []
        self.presses = 0
        self.releases = 0
        self.esc_callback = None

    def start_esc_listener(self, on_esc_callback):
        self.esc_callback = on_esc_callback

    def stop_esc_listener(self):
        pass

    def move_to(self, x, y):
        self.moves.append((x, y))

    def press_left_button(self):
        self.presses += 1

    def release_left_button(self):
        self.releases += 1

    def safe_reset(self):
        self.releases += 1


@pytest.fixture
def fake_engine(monkeypatch):
    """Patches the engine's mouse and timing so a drawing runs instantly."""
    mouse = FakeMouse()

    class FakeMouseController:
        """Stands in for the class: constructing it hands back the shared fake."""
        esc_down = False

        def __new__(cls, *_args, **_kwargs):
            return mouse

        @staticmethod
        def check_esc_pressed():
            return FakeMouseController.esc_down

    monkeypatch.setattr("src.drawing_engine.MouseController", FakeMouseController)
    monkeypatch.setattr("src.drawing_engine.precise_sleep", lambda _seconds: None)
    mouse.controller_class = FakeMouseController
    return mouse


def _run_worker(worker, timeout_ms=15000):
    """Runs a QThread worker to completion, collecting its signals."""
    events = {"finished": [], "cancelled": [], "error": [], "progress": []}
    loop = QEventLoop()

    worker.drawing_finished.connect(lambda *a: (events["finished"].append(a), loop.quit()))
    worker.drawing_cancelled.connect(lambda *a: (events["cancelled"].append(a), loop.quit()))
    worker.drawing_error.connect(lambda *a: (events["error"].append(a), loop.quit()))
    worker.progress_changed.connect(lambda *a: events["progress"].append(a))

    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(timeout_ms)
    return events


def test_engine_draws_every_point_with_the_area_offset(qapp, fake_engine):
    strokes = [[(0, 0), (5, 0), (10, 0)], [(2, 2), (2, 8)]]
    worker = DrawingEngineWorker(strokes, start_x=100, start_y=200, speed=100)

    events = _run_worker(worker)

    assert len(events["finished"]) == 1
    elapsed, total_strokes, total_points = events["finished"][0]
    assert (total_strokes, total_points) == (2, 5)
    assert elapsed >= 0
    assert fake_engine.presses == 2
    assert fake_engine.moves[0] == (100, 200)
    assert fake_engine.moves == [(100 + x, 200 + y) for s in strokes for x, y in s]


def test_engine_releases_the_button_for_every_press(qapp, fake_engine):
    worker = DrawingEngineWorker([[(0, 0), (1, 1)]] * 4, 0, 0, speed=100)
    _run_worker(worker)
    assert fake_engine.presses == 4
    assert fake_engine.releases >= fake_engine.presses


def test_engine_skips_strokes_shorter_than_two_points(qapp, fake_engine):
    worker = DrawingEngineWorker([[(1, 1)], [], [(0, 0), (3, 3)]], 0, 0, speed=100)
    events = _run_worker(worker)
    assert events["finished"][0][1] == 1
    assert fake_engine.presses == 1


def test_engine_reports_no_work_for_an_empty_drawing(qapp, fake_engine):
    events = _run_worker(DrawingEngineWorker([], 0, 0))
    assert events["finished"] == [(0.0, 0, 0)]


def test_engine_progress_is_monotonic_and_ends_at_100(qapp, fake_engine):
    strokes = [[(i, i), (i + 1, i + 1), (i + 2, i + 2)] for i in range(40)]
    worker = DrawingEngineWorker(strokes, 0, 0, speed=100)

    events = _run_worker(worker)

    assert events["progress"], "no progress was reported"
    percentages = [p[2] for p in events["progress"]]
    assert percentages == sorted(percentages)
    assert percentages[-1] == 100
    assert all(0 <= p <= 100 for p in percentages)
    # Remaining time must never be negative.
    assert all(p[4] >= 0 for p in events["progress"])


def test_engine_stops_when_asked(qapp, fake_engine):
    strokes = [[(i, i), (i + 1, i + 1)] for i in range(4000)]
    worker = DrawingEngineWorker(strokes, 0, 0, speed=100)
    worker.stop()

    events = _run_worker(worker)

    assert events["cancelled"], "cancellation was not reported"
    assert not events["finished"]
    assert len(fake_engine.moves) < len(strokes)


def test_engine_stops_on_the_esc_key(qapp, fake_engine):
    strokes = [[(i, i), (i + 1, i + 1)] for i in range(500)]
    fake_engine.controller_class.esc_down = True
    worker = DrawingEngineWorker(strokes, 0, 0, speed=100)

    events = _run_worker(worker)

    assert events["cancelled"]
    assert "ESC" in events["cancelled"][0][0]


def test_engine_reports_errors_instead_of_crashing(qapp, monkeypatch, fake_engine):
    def boom(*_args):
        raise RuntimeError("input device exploded")

    monkeypatch.setattr(fake_engine, "move_to", boom)
    worker = DrawingEngineWorker([[(0, 0), (1, 1)]], 0, 0, speed=100)

    events = _run_worker(worker)

    assert events["error"] and "exploded" in events["error"][0][0]
    assert fake_engine.releases >= 1, "the mouse button must be released on error"


# ---------------- processing worker ----------------

def _run_processor(worker, timeout_ms=30000):
    results = {"finished": [], "error": [], "cancelled": []}
    loop = QEventLoop()
    worker.processing_finished.connect(lambda *a: (results["finished"].append(a), loop.quit()))
    worker.processing_error.connect(lambda *a: (results["error"].append(a), loop.quit()))
    worker.processing_cancelled.connect(lambda *a: (results["cancelled"].append(a), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(timeout_ms)
    return results


def test_processor_worker_reports_results_with_its_request_id(qapp, sample_bgr):
    worker = ImageProcessorWorker(sample_bgr, 300, 220, quality_level="media", request_id=42)
    results = _run_processor(worker)

    assert results["finished"], results
    strokes, estimated, total_points, request_id = results["finished"][0]
    assert request_id == 42
    assert strokes and total_points == sum(len(s) for s in strokes)
    assert estimated > 0


def test_processor_worker_reports_errors(qapp):
    worker = ImageProcessorWorker("not an image", 300, 220, request_id=7)
    results = _run_processor(worker)

    assert results["error"], results
    assert results["error"][0][1] == 7


def test_processor_worker_reports_cancellation(qapp, sample_bgr):
    worker = ImageProcessorWorker(sample_bgr, 900, 700, quality_level="alta", request_id=3)
    worker.cancel()
    results = _run_processor(worker)

    assert results["cancelled"] == [(3,)]
    assert not results["finished"]
