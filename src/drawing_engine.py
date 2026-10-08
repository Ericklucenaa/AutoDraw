import time
from typing import List, Tuple
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from src.mouse_controller import MouseController
from src.time_estimator import TimeEstimator


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
        strokes: List[List[Tuple[int, int]]],
        start_x: int,
        start_y: int,
        speed: int = 50,
        estimated_total_seconds: float = 0.0,
        parent=None
    ):
        super().__init__(parent)
        self.strokes = strokes
        self.start_x = start_x
        self.start_y = start_y
        self.speed = max(1, min(100, speed))
        self.estimated_total_seconds = estimated_total_seconds

        self.mouse = MouseController()
        self._is_paused = False
        self._is_stopped = False
        
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

        self.drag_delay = 0.0025 - (self.speed / 100.0) * 0.0024

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

    def run(self) -> None:
        total_strokes = len(self.strokes)
        total_points = sum(len(s) for s in self.strokes)

        if total_strokes == 0:
            self.drawing_finished.emit(0.0, 0, 0)
            return

        self.mouse.start_esc_listener(on_esc_callback=self.stop)
        start_time = time.time()

        try:
            for i, stroke in enumerate(self.strokes):
                if self._is_stopped or MouseController.check_esc_pressed():
                    self.mouse.safe_reset()
                    self.drawing_cancelled.emit("Interrompido pelo usuário (ESC)")
                    return

                self._mutex.lock()
                while self._is_paused and not self._is_stopped:
                    self._pause_condition.wait(self._mutex)
                is_stopped = self._is_stopped
                self._mutex.unlock()

                if is_stopped or MouseController.check_esc_pressed():
                    self.mouse.safe_reset()
                    self.drawing_cancelled.emit("Interrompido pelo usuário")
                    return

                if len(stroke) < 2:
                    continue

                # 1. Move to starting position of stroke (mouse button UP)
                first_pt = stroke[0]
                target_x = self.start_x + first_pt[0]
                target_y = self.start_y + first_pt[1]
                
                self.mouse.move_to(target_x, target_y)
                time.sleep(0.004)

                # 2. Press left mouse button
                self.mouse.press_left_button()
                time.sleep(0.002)

                # 3. Drag mouse along interpolated dense stroke points
                for pt in stroke[1:]:
                    if self._is_stopped or MouseController.check_esc_pressed():
                        self.mouse.safe_reset()
                        self.drawing_cancelled.emit("Interrompido pelo usuário (ESC)")
                        return

                    target_x = self.start_x + pt[0]
                    target_y = self.start_y + pt[1]
                    self.mouse.move_to(target_x, target_y)
                    
                    if self.drag_delay > 0:
                        time.sleep(self.drag_delay)

                # 4. Release left mouse button at end of stroke
                self.mouse.release_left_button()
                time.sleep(0.002)

                # Calculate progress metrics
                elapsed_sec = time.time() - start_time
                pct = int(((i + 1) / total_strokes) * 100)
                
                # Estimate remaining time based on actual speed per stroke
                stroke_rate = (i + 1) / float(elapsed_sec) if elapsed_sec > 0 else 0
                if stroke_rate > 0:
                    remaining_sec = (total_strokes - (i + 1)) / stroke_rate
                else:
                    remaining_sec = max(0.0, self.estimated_total_seconds - elapsed_sec)

                self.progress_changed.emit(i + 1, total_strokes, pct, elapsed_sec, remaining_sec)

            actual_elapsed = time.time() - start_time
            self.drawing_finished.emit(actual_elapsed, total_strokes, total_points)

        except Exception as e:
            self.mouse.safe_reset()
            self.drawing_error.emit(f"Erro durante o desenho: {str(e)}")

        finally:
            self.mouse.safe_reset()
