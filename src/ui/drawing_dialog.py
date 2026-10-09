import time

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout
)

from src.logger import get_logger
from src.time_estimator import TimeEstimator
from src.ui.styles import ModernStyles

QUALITY_LABELS = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}

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
        self.setWindowTitle("AutoDraw — Desenhando...")
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
        self.start_time = time.time()

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        self.lbl_title = QLabel("🎨 Desenhando...", self)
        self.lbl_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #6366F1;")
        layout.addWidget(self.lbl_title)

        progress_card = QFrame(self)
        progress_card.setObjectName("Card")
        p_layout = QVBoxLayout(progress_card)
        p_layout.setContentsMargins(16, 16, 16, 16)
        p_layout.setSpacing(8)

        self.lbl_percentage = QLabel("0% concluído", self)
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
        self.lbl_time_rem = QLabel("Tempo restante: --", self)
        self.lbl_time_rem.setStyleSheet("color: #CBD5E1; font-weight: 600; font-size: 12px;")
        info_row.addWidget(self.lbl_time_rem)
        info_row.addStretch()
        self.lbl_stroke_count = QLabel(f"Traço: 0 / {self.total_strokes:,}", self)
        self.lbl_stroke_count.setStyleSheet("color: #94A3B8; font-size: 12px;")
        info_row.addWidget(self.lbl_stroke_count)
        p_layout.addLayout(info_row)

        self.lbl_total_est = QLabel(
            f"Tempo total estimado: {TimeEstimator.format_time(self.estimated_total_sec)}", self
        )
        self.lbl_total_est.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_total_est.setStyleSheet("color: #64748B; font-size: 11px;")
        p_layout.addWidget(self.lbl_total_est)

        layout.addWidget(progress_card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_pause = QPushButton("⏸️ PAUSAR", self)
        self.btn_pause.setFixedHeight(40)
        self.btn_pause.clicked.connect(self._toggle_pause)
        btn_layout.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("🛑 PARAR", self)
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.clicked.connect(self._request_stop)
        btn_layout.addWidget(self.btn_stop)

        layout.addLayout(btn_layout)

        lbl_hint = QLabel("⚡ Pressione ESC a qualquer momento para cancelar", self)
        lbl_hint.setObjectName("BadgeWarning")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_hint)

    @Slot(int, int, int, float, float)
    def update_progress(
        self, current: int, total: int, percentage: int, elapsed_sec: float, remaining_sec: float
    ):
        self.progress_bar.setValue(percentage)
        self.lbl_percentage.setText(f"{percentage}% concluído")
        self.lbl_stroke_count.setText(f"Traço: {current:,} / {total:,}")
        self.lbl_time_rem.setText(
            f"Restante: {TimeEstimator.format_time(remaining_sec)}"
            f"  ·  Decorrido: {TimeEstimator.format_time(elapsed_sec)}"
        )

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.lbl_title.setText("⏸️ Desenho Pausado")
            self.lbl_title.setStyleSheet("color: #FBBF24;")
            self.btn_pause.setText("▶️ CONTINUAR")
            self.btn_pause.setStyleSheet("background-color: #059669; color: white;")
            self.pause_requested.emit()
        else:
            self.lbl_title.setText("🎨 Desenhando...")
            self.lbl_title.setStyleSheet("color: #6366F1;")
            self.btn_pause.setText("⏸️ PAUSAR")
            self.btn_pause.setStyleSheet("")
            self.resume_requested.emit()

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
        self.setWindowTitle("🎉 Desenho Concluído!")
        self.setFixedWidth(420)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.elapsed_seconds = elapsed_seconds
        self.quality_level = QUALITY_LABELS.get(quality_level.lower(), quality_level.capitalize())
        self.total_strokes = total_strokes
        self.total_points = total_points
        self.repeat_chosen = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        lbl_title = QLabel("🎉 Desenho Concluído!", self)
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
            f"⏱ <b>Tempo real utilizado:</b> {TimeEstimator.format_time(self.elapsed_seconds)}", self
        ))
        c_layout.addWidget(QLabel(f"⭐ <b>Qualidade:</b> {self.quality_level}", self))
        c_layout.addWidget(QLabel(
            f"🖌️ <b>Traços realizados:</b> {self.total_strokes:,}"
            + (f" &nbsp;·&nbsp; <b>Pontos:</b> {self.total_points:,}" if self.total_points else ""),
            self,
        ))

        layout.addWidget(card)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_new = QPushButton("🆕 NOVO DESENHO", self)
        btn_new.setFixedHeight(42)
        btn_new.clicked.connect(self.accept)
        btn_layout.addWidget(btn_new)

        btn_repeat = QPushButton("🔄 REPETIR DESENHO", self)
        btn_repeat.setObjectName("PrimaryButton")
        btn_repeat.setFixedHeight(42)
        btn_repeat.setToolTip("Redesenha na mesma área, com nova contagem regressiva.")
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
