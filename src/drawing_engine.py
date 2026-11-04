import time
from typing import List, Tuple

from PySide6.QtCore import QMutex, QThread, QWaitCondition, Signal

from src.logger import get_logger
from src.mouse_controller import MouseController, TimerResolution, precise_sleep
from src.time_estimator import (
    PEN_SETTLE_AFTER_PRESS,
    PEN_SETTLE_AFTER_RELEASE,
    PEN_SETTLE_BEFORE_PRESS,
    TimeEstimator,
    drag_delay_for_speed,
)

log = get_logger("engine")

Stroke = List[Tuple[int, int]]

ESC_REASON = "Interrompido pelo usuário (ESC)"
STOP_REASON = "Parado pelo usuário"
# After Continue, wait this long before taking the mouse back, so the hand
# that just clicked the button has time to leave the mouse.
RESUME_DELAY_SEC = 0.6

# Progress is emitted at most this often; a drawing can contain hundreds of
# thousands of points and one signal per point would swamp the UI thread.
PROGRESS_INTERVAL_SEC = 0.05


class DrawingEngineWorker(QThread):
    """
    QThread worker that performs the mouse drawing operations asynchronously,
    handling pause/resume/stop states, remaining time calculation, and signaling UI.
    """
    # current_stroke, total_strokes, percent, elapsed_sec, remaining_sec
    progress_changed = Signal(int, int, int, float, float)
    drawing_finished = Signal(float, int, int)  # actual_elapsed_seconds, total_strokes, total_points
    drawing_paused = Signal()
    drawing_resumed = Signal()
    drawing_cancelled = Signal(str)
    drawing_error = Signal(str)

    def __init__(
        self,
        strokes: List[Stroke],
        start_x: int,
        start_y: int,
        speed: int = 50,
        estimated_total_seconds: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.strokes = [s for s in strokes if len(s) >= 2]
        self.start_x = start_x
        self.start_y = start_y
        self.speed = max(1, min(100, speed))
        self.estimated_total_seconds = estimated_total_seconds

        self.mouse = MouseController()
        self._is_paused = False
        self._is_stopped = False
        self._stop_reason = STOP_REASON
        self._paused_total = 0.0

        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

        self.drag_delay = drag_delay_for_speed(self.speed)
        self.total_points = sum(len(s) for s in self.strokes)

    # ---------------- control ----------------

    def pause(self) -> None:
        """
        Pauses drawing execution.

        The worker notices the flag on its very next point, lifts the pen and
        waits there; on resume it puts the pen back down on that same point,
        so the stroke continues without a gap.
        """
        self._mutex.lock()
        already = self._is_paused
        self._is_paused = True
        self._mutex.unlock()
        if not already:
            self.drawing_paused.emit()

    def resume(self) -> None:
        """Resumes drawing execution."""
        self._mutex.lock()
        was_paused = self._is_paused
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        if was_paused:
            self.drawing_resumed.emit()

    def stop(self, reason: str = STOP_REASON) -> None:
        """Stops and cancels drawing execution."""
        self._mutex.lock()
        if not self._is_stopped:
            self._stop_reason = reason
        self._is_stopped = True
        if self._is_paused:
            self._is_paused = False
            self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.mouse.safe_reset()

    def _state(self) -> str:
        """'stop', 'pause' or '' for the point about to be drawn."""
        self._mutex.lock()
        stopped, paused = self._is_stopped, self._is_paused
        self._mutex.unlock()
        if stopped:
            return "stop"
        if MouseController.check_esc_pressed():
            self._mutex.lock()
            self._stop_reason = ESC_REASON
            self._is_stopped = True
            self._mutex.unlock()
            return "stop"
        return "pause" if paused else ""

    def _wait_while_paused(self) -> bool:
        """Blocks while paused; returns True if the worker should abort."""
        began = time.time()
        self._mutex.lock()
        waited = self._is_paused
        while self._is_paused and not self._is_stopped:
            self._pause_condition.wait(self._mutex)
        stopped = self._is_stopped
        self._mutex.unlock()
        if waited and not stopped:
            time.sleep(RESUME_DELAY_SEC)
            stopped = self._state() == "stop"
        if waited:
            self._paused_total += time.time() - began
        return stopped

    def _hold_pen_while_paused(self, x: int, y: int) -> bool:
        """
        Lifts the pen at (x, y), waits out the pause and puts it back down on
        the same spot. Returns True if the drawing was stopped meanwhile.
        """
        self.mouse.release_left_button()
        if self._wait_while_paused():
            return True
        self.mouse.move_to(x, y)
        precise_sleep(PEN_SETTLE_BEFORE_PRESS)
        self.mouse.press_left_button()
        precise_sleep(PEN_SETTLE_AFTER_PRESS)
        return False

        # ---------------- execution ----------------

    def run(self) -> None:
        total_strokes = len(self.strokes)
        if total_strokes == 0:
            self.drawing_finished.emit(0.0, 0, 0)
            return

        log.info("Drawing %d strokes / %d points at speed %d", total_strokes, self.total_points, self.speed)
        self.mouse.start_esc_listener(on_esc_callback=lambda: self.stop(ESC_REASON))
        begin_session = getattr(self.mouse, "begin_session", None)
        if begin_session is not None:
            begin_session()
        start_time = time.time()
        points_done = 0
        last_emit = 0.0
        ox, oy = self.start_x, self.start_y

        try:
            # A 1ms system timer makes the short per-point delays achievable.
            with TimerResolution():
                for index, stroke in enumerate(self.strokes):
                    if self._wait_while_paused() or self._state() == "stop":
                        return self._cancel()

                    # 1. Move to the stroke start with the button up.
                    self.mouse.move_to(ox + stroke[0][0], oy + stroke[0][1])
                    precise_sleep(PEN_SETTLE_BEFORE_PRESS)

                    # 2. Press the left button.
                    self.mouse.press_left_button()
                    precise_sleep(PEN_SETTLE_AFTER_PRESS)
                    points_done += 1
                    last = stroke[0]

                    # 3. Drag along the densified stroke.
                    for point in stroke[1:]:
                        state = self._state()
                        if state == "pause":
                            # Resume from the last point actually drawn.
                            if self._hold_pen_while_paused(ox + last[0], oy + last[1]):
                                return self._cancel()
                        elif state == "stop":
                            return self._cancel()

                        self.mouse.move_to(ox + point[0], oy + point[1])
                        precise_sleep(self.drag_delay)
                        points_done += 1
                        last = point

                        now = time.time()
                        if now - last_emit >= PROGRESS_INTERVAL_SEC:
                            last_emit = now
                            self._emit_progress(index, total_strokes, points_done, self._active(start_time, now))

                    # 4. Release at the end of the stroke.
                    self.mouse.release_left_button()
                    precise_sleep(PEN_SETTLE_AFTER_RELEASE)

                    now = time.time()
                    if now - last_emit >= PROGRESS_INTERVAL_SEC or index == total_strokes - 1:
                        last_emit = now
                        self._emit_progress(index, total_strokes, points_done, self._active(start_time, now))

            # Time spent paused is not drawing time: leaving it in would skew
            # the calibration of the next estimate.
            actual_elapsed = self._active(start_time, time.time())
            log.info("Drawing finished in %.1fs", actual_elapsed)
            self.drawing_finished.emit(actual_elapsed, total_strokes, self.total_points)

        except Exception as e:
            log.exception("Drawing failed")
            self.mouse.safe_reset()
            self.drawing_error.emit(f"Erro durante o desenho: {e}")

        finally:
            self.mouse.safe_reset()
            end_session = getattr(self.mouse, "end_session", None)
            if end_session is not None:
                end_session()

    def _active(self, start_time: float, now: float) -> float:
        """Elapsed drawing time, excluding pauses."""
        return max(0.0, now - start_time - self._paused_total)

    def _emit_progress(self, index: int, total_strokes: int, points_done: int, elapsed: float) -> None:
        percent = int(min(100, points_done * 100 / self.total_points)) if self.total_points else 0
        remaining = TimeEstimator.remaining_seconds(
            points_done=points_done,
            points_total=self.total_points,
            elapsed_seconds=elapsed,
            fallback_total=self.estimated_total_seconds,
        )
        self.progress_changed.emit(index + 1, total_strokes, percent, elapsed, remaining)

    def _cancel(self) -> None:
        self._mutex.lock()
        reason = self._stop_reason
        self._mutex.unlock()
        log.info("Drawing cancelled: %s", reason)
        self.mouse.safe_reset()
        self.drawing_cancelled.emit(reason)
