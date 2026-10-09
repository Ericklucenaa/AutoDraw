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

        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

        self.drag_delay = drag_delay_for_speed(self.speed)
        self.total_points = sum(len(s) for s in self.strokes)

    # ---------------- control ----------------

    def pause(self) -> None:
        """Pauses drawing execution."""
        self._mutex.lock()
        self._is_paused = True
        self._mutex.unlock()
        self.mouse.release_left_button()
        self.drawing_paused.emit()

    def resume(self) -> None:
        """Resumes drawing execution."""
        self._mutex.lock()
        self._is_paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.drawing_resumed.emit()

    def stop(self) -> None:
        """Stops and cancels drawing execution."""
        self._mutex.lock()
        self._is_stopped = True
        if self._is_paused:
            self._is_paused = False
            self._pause_condition.wakeAll()
        self._mutex.unlock()
        self.mouse.safe_reset()

    def _should_abort(self) -> bool:
        """True when the user asked to stop, via the UI or the ESC key."""
        self._mutex.lock()
        stopped = self._is_stopped
        self._mutex.unlock()
        return stopped or MouseController.check_esc_pressed()

    def _wait_while_paused(self) -> bool:
        """Blocks while paused; returns True if the worker should abort."""
        self._mutex.lock()
        while self._is_paused and not self._is_stopped:
            self._pause_condition.wait(self._mutex)
        stopped = self._is_stopped
        self._mutex.unlock()
        return stopped

    # ---------------- execution ----------------

    def run(self) -> None:
        total_strokes = len(self.strokes)
        if total_strokes == 0:
            self.drawing_finished.emit(0.0, 0, 0)
            return

        log.info("Drawing %d strokes / %d points at speed %d", total_strokes, self.total_points, self.speed)
        self.mouse.start_esc_listener(on_esc_callback=self.stop)
        start_time = time.time()
        points_done = 0
        last_emit = 0.0

        try:
            # A 1ms system timer makes the short per-point delays achievable.
            with TimerResolution():
                for index, stroke in enumerate(self.strokes):
                    if self._wait_while_paused() or self._should_abort():
                        return self._cancel("Interrompido pelo usuário (ESC)")

                    # 1. Move to the stroke start with the button up.
                    self.mouse.move_to(self.start_x + stroke[0][0], self.start_y + stroke[0][1])
                    precise_sleep(PEN_SETTLE_BEFORE_PRESS)

                    # 2. Press the left button.
                    self.mouse.press_left_button()
                    precise_sleep(PEN_SETTLE_AFTER_PRESS)
                    points_done += 1

                    # 3. Drag along the densified stroke.
                    for point in stroke[1:]:
                        if self._should_abort():
                            return self._cancel("Interrompido pelo usuário (ESC)")

                        self.mouse.move_to(self.start_x + point[0], self.start_y + point[1])
                        precise_sleep(self.drag_delay)
                        points_done += 1

                        now = time.time()
                        if now - last_emit >= PROGRESS_INTERVAL_SEC:
                            last_emit = now
                            self._emit_progress(index, total_strokes, points_done, now - start_time)

                    # 4. Release at the end of the stroke.
                    self.mouse.release_left_button()
                    precise_sleep(PEN_SETTLE_AFTER_RELEASE)

                    now = time.time()
                    if now - last_emit >= PROGRESS_INTERVAL_SEC or index == total_strokes - 1:
                        last_emit = now
                        self._emit_progress(index, total_strokes, points_done, now - start_time)

            actual_elapsed = time.time() - start_time
            log.info("Drawing finished in %.1fs", actual_elapsed)
            self.drawing_finished.emit(actual_elapsed, total_strokes, self.total_points)

        except Exception as e:
            log.exception("Drawing failed")
            self.mouse.safe_reset()
            self.drawing_error.emit(f"Erro durante o desenho: {e}")

        finally:
            self.mouse.safe_reset()

    def _emit_progress(self, index: int, total_strokes: int, points_done: int, elapsed: float) -> None:
        percent = int(min(100, points_done * 100 / self.total_points)) if self.total_points else 0
        remaining = TimeEstimator.remaining_seconds(
            points_done=points_done,
            points_total=self.total_points,
            elapsed_seconds=elapsed,
            fallback_total=self.estimated_total_seconds,
        )
        self.progress_changed.emit(index + 1, total_strokes, percent, elapsed, remaining)

    def _cancel(self, reason: str) -> None:
        log.info("Drawing cancelled: %s", reason)
        self.mouse.safe_reset()
        self.drawing_cancelled.emit(reason)
