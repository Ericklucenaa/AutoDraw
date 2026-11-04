"""Pause without gaps, the real-mouse guard, exact SendInput mapping and dialog placement."""
import threading

import pytest
from PySide6.QtCore import QEventLoop, QRect, QTimer

from src.drawing_engine import DrawingEngineWorker
from src.input_guard import MovementMeter, RealMouseGuard
from src.mouse_controller import MouseController
from src.ui.drawing_dialog import _corner_candidates, _overlap


# ---------------- engine: pause and stop ----------------

class LoggingMouse:
    """Fake mouse that records every action in order."""

    def __init__(self):
        self.log = []
        self.on_move = None

    def start_esc_listener(self, on_esc_callback):
        pass

    def stop_esc_listener(self):
        pass

    def move_to(self, x, y):
        self.log.append(("move", x, y))
        if self.on_move:
            self.on_move(len([e for e in self.log if e[0] == "move"]))

    def press_left_button(self):
        self.log.append(("down",))

    def release_left_button(self):
        self.log.append(("up",))

    def safe_reset(self):
        self.log.append(("up",))


@pytest.fixture
def logging_mouse(monkeypatch):
    mouse = LoggingMouse()

    class Controller:
        def __new__(cls, *_a, **_k):
            return mouse

        @staticmethod
        def check_esc_pressed():
            return False

    monkeypatch.setattr("src.drawing_engine.MouseController", Controller)
    monkeypatch.setattr("src.drawing_engine.precise_sleep", lambda _s: None)
    monkeypatch.setattr("src.drawing_engine.RESUME_DELAY_SEC", 0.0)
    return mouse


def _run(worker, timeout_ms=15000):
    events = {"finished": [], "cancelled": [], "error": []}
    loop = QEventLoop()
    worker.drawing_finished.connect(lambda *a: (events["finished"].append(a), loop.quit()))
    worker.drawing_cancelled.connect(lambda *a: (events["cancelled"].append(a), loop.quit()))
    worker.drawing_error.connect(lambda *a: (events["error"].append(a), loop.quit()))
    QTimer.singleShot(timeout_ms, loop.quit)
    worker.start()
    loop.exec()
    worker.wait(timeout_ms)
    return events


def _drawn_segments(log):
    """Pen-down segments as lists of points, reconstructed from the action log."""
    segments, current, down, pos = [], None, False, None
    for entry in log:
        if entry[0] == "move":
            pos = (entry[1], entry[2])
            if down:
                current.append(pos)
        elif entry[0] == "down" and not down:
            down, current = True, [pos]
        elif entry[0] == "up" and down:
            down = False
            segments.append(current)
    return segments


def test_pause_mid_stroke_lifts_the_pen_and_resumes_on_the_same_point(qapp, logging_mouse):
    stroke = [(x, 0) for x in range(10)]
    worker = DrawingEngineWorker([stroke], 0, 0, speed=100)

    def on_move(count):
        if count == 4:
            worker.pause()
            threading.Timer(0.1, worker.resume).start()

    logging_mouse.on_move = on_move
    events = _run(worker)

    assert events["finished"]
    segments = _drawn_segments(logging_mouse.log)
    assert len(segments) == 2, "the pen must be lifted during the pause"
    first, second = segments
    # The second segment starts exactly where the first one stopped: no gap.
    assert second[0] == first[-1]
    drawn = first + second[1:]
    assert drawn == stroke


def test_paused_time_is_not_counted_as_drawing_time(qapp, logging_mouse):
    worker = DrawingEngineWorker([[(x, 0) for x in range(6)]], 0, 0, speed=100)

    def on_move(count):
        if count == 2:
            worker.pause()
            threading.Timer(0.4, worker.resume).start()

    logging_mouse.on_move = on_move
    events = _run(worker)

    elapsed = events["finished"][0][0]
    assert elapsed < 0.3


def test_stop_reports_the_reason_given(qapp, logging_mouse):
    worker = DrawingEngineWorker([[(x, 0) for x in range(50)]], 0, 0, speed=100)
    logging_mouse.on_move = lambda count: count == 3 and worker.stop("mouse mexido")
    events = _run(worker)
    assert events["cancelled"] and "mouse mexido" in events["cancelled"][0][0]


def test_stop_while_paused_cancels(qapp, logging_mouse):
    worker = DrawingEngineWorker([[(x, 0) for x in range(50)]], 0, 0, speed=100)

    def on_move(count):
        if count == 3:
            worker.pause()
            threading.Timer(0.1, worker.stop).start()

    logging_mouse.on_move = on_move
    events = _run(worker)
    assert events["cancelled"] and not events["finished"]
    assert logging_mouse.log[-1] == ("up",)


# ---------------- SendInput mapping ----------------

@pytest.mark.parametrize("size", [1366, 1920, 2560, 3840, 4480, 5120, 7680])
def test_normalize_lands_on_the_exact_pixel(size):
    """Windows maps back with floor(n * size / 65536); every pixel must round-trip."""
    for px in range(size):
        n = MouseController.normalize(px, 0, size)
        assert 0 <= n <= 65535
        assert (n * size) >> 16 == px


def test_normalize_handles_monitors_left_of_the_primary():
    # Virtual desktop starting at x = -1920 (a monitor to the left).
    n = MouseController.normalize(-1920 + 100, -1920, 3840)
    assert (n * 3840) >> 16 == 100


# ---------------- real-mouse guard ----------------

def test_meter_ignores_small_bumps_and_fires_on_real_movement():
    meter = MovementMeter(threshold=40, window_sec=1.0)
    assert not meter.add(10, now=0.0)
    assert not meter.add(10, now=0.5)
    assert not meter.add(15, now=1.6)  # the first two left the window
    assert meter.add(30, now=1.7)


def _guard():
    fired = []
    return RealMouseGuard(on_touch=fired.append), fired


def test_guard_ignores_injected_events():
    guard, fired = _guard()
    for _ in range(100):
        guard.feed(is_real=False, button_down=False, movement=50)
    guard.feed(is_real=False, button_down=True, movement=0)
    assert fired == []


def test_guard_fires_on_real_movement_and_clicks():
    guard, fired = _guard()
    guard.feed(is_real=True, button_down=False, movement=60)
    assert fired == ["mouse mexido"]

    guard, fired = _guard()
    guard.feed(is_real=True, button_down=True, movement=0)
    assert fired == ["clique do mouse"]


def test_guard_fires_once_and_stays_quiet_while_suspended():
    guard, fired = _guard()
    guard.feed(True, False, 60)
    guard.feed(True, False, 60)
    assert len(fired) == 1
    guard.suspend()
    guard.feed(True, True, 100)
    assert len(fired) == 1


def test_guard_resume_has_a_grace_period(monkeypatch):
    guard, fired = _guard()
    clock = {"t": 100.0}
    monkeypatch.setattr("src.input_guard.time.monotonic", lambda: clock["t"])
    guard.suspend()
    guard.resume(grace_sec=1.0)
    guard.feed(True, True, 0)          # the click on Continue itself
    assert fired == []
    clock["t"] += 1.5
    guard.feed(True, True, 0)
    assert fired == ["clique do mouse"]


# ---------------- dialog placement ----------------

class FakeScreen:
    def __init__(self, geo, ratio=1.0, work=None):
        self._geo, self._ratio, self._work = geo, ratio, work or geo

    def geometry(self):
        return self._geo

    def availableGeometry(self):
        return self._work

    def devicePixelRatio(self):
        return self._ratio


def test_overlap():
    assert _overlap((0, 0, 10, 10), (20, 20, 5, 5)) == 0
    assert _overlap((0, 0, 10, 10), (5, 5, 10, 10)) == 25
    assert _overlap((0, 0, 10, 10), (12, 0, 5, 5), margin=4) > 0


def test_a_free_corner_is_found_on_the_same_screen():
    screen = FakeScreen(QRect(0, 0, 1920, 1080), work=QRect(0, 0, 1920, 1040))
    area = (100, 100, 800, 600)  # top-left part of the screen
    free = [phys for _, phys in _corner_candidates(460, 340, area, [screen]) if not _overlap(phys, area, 16)]
    assert free, "a corner away from the area must exist"


def test_scaled_screens_are_mapped_to_physical_pixels():
    # 150% scaling: Qt reports 2560x1440 physical as 1707x960 logical at the same origin.
    screen = FakeScreen(QRect(0, 0, 1707, 960), ratio=1.5)
    candidates = list(_corner_candidates(400, 300, (0, 0, 10, 10), [screen]))
    _, phys = candidates[0]  # bottom-right
    assert phys[2] == 600 and phys[3] == 450
    assert phys[0] + phys[2] <= 2560 and phys[1] + phys[3] <= 1440


def test_the_screen_holding_the_area_comes_first():
    left = FakeScreen(QRect(0, 0, 1920, 1080))
    right = FakeScreen(QRect(1920, 0, 1920, 1080))
    area = (2500, 300, 400, 300)
    logical, _ = next(_corner_candidates(400, 300, area, [left, right]))
    assert logical.x() >= 1920
