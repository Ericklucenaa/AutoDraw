import time

from typing import Iterable, Optional, Tuple

from PySide6.QtCore import QRect, Qt, Signal, Slot
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout
)

from src.i18n import tr
from src.logger import get_logger
from src.time_estimator import TimeEstimator
from src.ui.styles import ModernStyles

QUALITY_SOURCE = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}

log = get_logger("ui.progress")

try:  # Windows-only; the module must still import for tests on other platforms.
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


def play_finish_sound() -> None:
    if winsound is None:
        return
    try:
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except (RuntimeError, OSError):
        log.debug("Could not play completion sound", exc_info=True)


HINT_DRAWING = "⚡ ESC cancela · mexer ou clicar com o mouse pausa o desenho"
# Gap kept between the dialog and the drawing area, in physical pixels.
CORNER_MARGIN = 16


def _overlap(rect: Tuple[int, int, int, int], area: Tuple[int, int, int, int], margin: int = 0) -> int:
    """Overlapping area, in px², of two (x, y, w, h) rectangles; area grown by margin."""
    ax, ay, aw, ah = area[0] - margin, area[1] - margin, area[2] + 2 * margin, area[3] + 2 * margin
    x, y, w, h = rect
    dx = min(x + w, ax + aw) - max(x, ax)
    dy = min(y + h, ay + ah) - max(y, ay)
    return dx * dy if dx > 0 and dy > 0 else 0


def _to_physical(screen_geo: QRect, ratio: float, logical: QRect) -> Tuple[int, int, int, int]:
    """
    Qt keeps each screen's top-left at its native position and divides only
    the size by the scale factor; map a logical rect on that screen back.
    """
    ox, oy = screen_geo.x(), screen_geo.y()
    return (
        int(ox + (logical.x() - ox) * ratio),
        int(oy + (logical.y() - oy) * ratio),
        int(logical.width() * ratio),
        int(logical.height() * ratio),
    )


def _corner_candidates(
    width: int, height: int, area: Tuple[int, int, int, int], screens: Optional[Iterable] = None
):
    """
    Yields (logical QRect, physical rect) for the four corners of every
    screen's work area, the screen holding the drawing area first.
    """
    screens = list(screens if screens is not None else QGuiApplication.screens())
    cx, cy = area[0] + area[2] // 2, area[1] + area[3] // 2

    def holds_area(screen) -> bool:
        x, y, w, h = _to_physical(screen.geometry(), screen.devicePixelRatio(), screen.geometry())
        return x <= cx < x + w and y <= cy < y + h

    screens.sort(key=lambda s: not holds_area(s))
    pad = 12
    for screen in screens:
        work = screen.availableGeometry()
        ratio = screen.devicePixelRatio()
        xs = (work.right() - width - pad, work.left() + pad)
        ys = (work.bottom() - height - pad, work.top() + pad)
        for y in ys:
            for x in xs:
                logical = QRect(x, y, width, height)
                yield logical, _to_physical(screen.geometry(), ratio, logical)


class DrawingProgressDialog(QDialog):
    """
    Modal progress dialog displayed while AutoDraw controls the mouse.
    Displays live progress %, remaining time, stroke counts, and pause/stop controls.
    """
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()

    def __init__(
        self,
        total_strokes: int,
        estimated_total_sec: float,
        sound_on_finish: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("AutoDraw — Desenhando..."))
        self.setFixedSize(460, 340)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.total_strokes = total_strokes
        self.estimated_total_sec = estimated_total_sec
        self.sound_on_finish = sound_on_finish
        self.is_paused = False
        self._click_through = False
        self.start_time = time.time()

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self.lbl_title = QLabel(tr("🎨 Desenhando..."), self)
        self.lbl_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #6366F1;")
        layout.addWidget(self.lbl_title)

        progress_card = QFrame(self)
        progress_card.setObjectName("Card")
        p_layout = QVBoxLayout(progress_card)
        p_layout.setContentsMargins(16, 16, 16, 16)
        p_layout.setSpacing(8)

        self.lbl_percentage = QLabel(tr("{percent}% concluído", percent=0), self)
        self.lbl_percentage.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.lbl_percentage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_percentage.setStyleSheet("color: #4ADE80;")
        p_layout.addWidget(self.lbl_percentage)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        p_layout.addWidget(self.progress_bar)

        info_row = QHBoxLayout()
        self.lbl_time_rem = QLabel(tr("Tempo restante: --"), self)
        self.lbl_time_rem.setStyleSheet("color: #CBD5E1; font-weight: 600; font-size: 12px;")
        info_row.addWidget(self.lbl_time_rem)
        info_row.addStretch()
        self.lbl_stroke_count = QLabel(tr("Traço: {current:,} / {total:,}", current=0, total=self.total_strokes), self)
        self.lbl_stroke_count.setStyleSheet("color: #94A3B8; font-size: 12px;")
        info_row.addWidget(self.lbl_stroke_count)
        p_layout.addLayout(info_row)

        self.lbl_total_est = QLabel(
            tr("Tempo total estimado: {time}", time=TimeEstimator.format_time(self.estimated_total_sec)), self
        )
        self.lbl_total_est.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_total_est.setStyleSheet("color: #64748B; font-size: 11px;")
        p_layout.addWidget(self.lbl_total_est)

        layout.addWidget(progress_card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_pause = QPushButton(tr("⏸️ PAUSAR"), self)
        self.btn_pause.setFixedHeight(40)
        self.btn_pause.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.btn_pause)

        self.btn_stop = QPushButton(tr("🛑 PARAR"), self)
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.clicked.connect(self._request_stop)
        btn_layout.addWidget(self.btn_stop)

        layout.addLayout(btn_layout)

        self.lbl_hint = QLabel(tr(HINT_DRAWING), self)
        self.lbl_hint.setObjectName("BadgeWarning")
        self.lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_hint.setWordWrap(True)
        layout.addWidget(self.lbl_hint)

    @Slot(int, int, int, float, float)
    def update_progress(
        self, current: int, total: int, percentage: int, elapsed_sec: float, remaining_sec: float
    ):
        self.progress_bar.setValue(percentage)
        self.lbl_percentage.setText(tr("{percent}% concluído", percent=percentage))
        self.lbl_stroke_count.setText(tr("Traço: {current:,} / {total:,}", current=current, total=total))
        self.lbl_time_rem.setText(
            tr("Restante: {remaining}  ·  Decorrido: {elapsed}",
               remaining=TimeEstimator.format_time(remaining_sec), elapsed=TimeEstimator.format_time(elapsed_sec))
        )

    def _toggle_pause(self):
        paused = not self.is_paused
        self.set_paused(paused)
        if paused:
            self.pause_requested.emit()
        else:
            self.resume_requested.emit()

    @Slot()
    def show_paused(self, reason: str = "") -> None:
        """Shows the paused state when the pause came from elsewhere (the mouse guard)."""
        self.set_paused(True, reason)

    def set_paused(self, paused: bool, reason: str = "") -> None:
        """Updates the controls without emitting anything."""
        self.is_paused = paused
        if paused:
            self.lbl_title.setText(tr("⏸️ Desenho pausado"))
            self.lbl_title.setStyleSheet("color: #FBBF24;")
            self.btn_pause.setText(tr("▶️ CONTINUAR"))
            self.btn_pause.setStyleSheet("background-color: #059669; color: white;")
            self.lbl_hint.setText(
                (tr("Pausado: {reason}.", reason=reason) + " " if reason else "")
                + tr("Clique em CONTINUAR e solte o mouse: o desenho volta do mesmo ponto.")
            )
        else:
            self.lbl_title.setText(tr("🎨 Desenhando..."))
            self.lbl_title.setStyleSheet("color: #6366F1;")
            self.btn_pause.setText(tr("⏸️ PAUSAR"))
            self.btn_pause.setStyleSheet("")
            self.lbl_hint.setText(tr(HINT_DRAWING))
        if self._click_through:
            # Over the canvas the dialog lets the drawing clicks through, but
            # while paused its buttons must be clickable.
            self._set_click_through(not paused)

    # ---------------- placement ----------------

    def place_outside(self, area: Tuple[int, int, int, int]) -> bool:
        """
        Moves the dialog to a screen corner that does not cover the drawing
        area (physical pixels). Returns False when no corner is free: the
        dialog then sits in the least covering corner and lets clicks pass
        through it to the canvas, so the drawing still lands where it should.
        """
        corners = list(_corner_candidates(self.width(), self.height(), area))
        if not corners:
            return True
        best, best_overlap = None, None
        for logical, physical in corners:
            overlap = _overlap(physical, area, margin=CORNER_MARGIN)
            if overlap == 0:
                self.move(logical.topLeft())
                return True
            if best_overlap is None or overlap < best_overlap:
                best, best_overlap = logical, overlap
        self.move(best.topLeft())
        self._click_through = True
        self._set_click_through(True)
        return False

    def _set_click_through(self, on: bool) -> None:
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, on)
        self.setWindowOpacity(0.82 if on else 1.0)
        if visible:
            self.show()

    def _request_stop(self):
        self.stop_requested.emit()
        self.reject()

    def on_finished(self):
        if self.sound_on_finish:
            play_finish_sound()
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._request_stop()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Closing the window must stop the mouse, never silently orphan it.
        if self.result() != QDialog.DialogCode.Accepted:
            self.stop_requested.emit()
        super().closeEvent(event)


class CompletionDialog(QDialog):
    """
    Modal displayed upon drawing completion with stats and 'REPETIR DESENHO' / 'NOVO DESENHO' choices.
    """
    repeat_requested = Signal()

    def __init__(
        self,
        elapsed_seconds: float,
        quality_level: str,
        total_strokes: int,
        total_points: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("🎉 Desenho concluído!"))
        self.setFixedWidth(420)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.elapsed_seconds = elapsed_seconds
        self.quality_level = tr(QUALITY_SOURCE.get(quality_level.lower(), quality_level.capitalize()))
        self.total_strokes = total_strokes
        self.total_points = total_points
        self.repeat_chosen = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        lbl_title = QLabel(tr("🎉 Desenho concluído!"), self)
        lbl_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #4ADE80;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        card = QFrame(self)
        card.setObjectName("Card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 16, 16, 16)
        c_layout.setSpacing(8)

        c_layout.addWidget(QLabel(
            tr("⏱ <b>Tempo real utilizado:</b> {time}", time=TimeEstimator.format_time(self.elapsed_seconds)), self
        ))
        c_layout.addWidget(QLabel(tr("⭐ <b>Qualidade:</b> {quality}", quality=self.quality_level), self))
        c_layout.addWidget(QLabel(
            tr("🖌️ <b>Traços realizados:</b> {strokes:,}", strokes=self.total_strokes)
            + (tr(" &nbsp;·&nbsp; <b>Pontos:</b> {points:,}", points=self.total_points) if self.total_points else ""),
            self,
        ))

        layout.addWidget(card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_new = QPushButton(tr("🆕 NOVO DESENHO"), self)
        btn_new.setFixedHeight(42)
        btn_new.clicked.connect(self.accept)
        btn_layout.addWidget(btn_new)

        btn_repeat = QPushButton(tr("🔄 REPETIR DESENHO"), self)
        btn_repeat.setObjectName("PrimaryButton")
        btn_repeat.setFixedHeight(42)
        btn_repeat.setToolTip(tr("Redesenha na mesma área, com nova contagem regressiva."))
        btn_repeat.clicked.connect(self._request_repeat)
        btn_layout.addWidget(btn_repeat)

        layout.addLayout(btn_layout)

    def _request_repeat(self):
        # Only record the choice here. Starting the next drawing from inside
        # this handler ran it nested in this dialog's event loop, stacking one
        # loop per repeat; the caller restarts after exec() returns instead.
        self.repeat_chosen = True
        self.repeat_requested.emit()
        self.accept()
