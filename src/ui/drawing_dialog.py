import time
import winsound
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QFrame
)

from src.time_estimator import TimeEstimator
from src.ui.styles import ModernStyles


class DrawingProgressDialog(QDialog):
    """
    Modal progress dialog displayed while AutoDraw controls the mouse.
    Displays live progress %, remaining time, stroke counts, and pause/stop controls.
    """
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()

    def __init__(self, total_strokes: int, estimated_total_sec: float, sound_on_finish: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AutoDraw — Desenhando...")
        self.setFixedWidth(460)
        self.setFixedHeight(340)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
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

        # Title
        self.lbl_title = QLabel("🎨 Desenhando...", self)
        self.lbl_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet("color: #6366F1;")
        layout.addWidget(self.lbl_title)

        # Progress Card
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

        # Time & Stroke details
        info_row = QHBoxLayout()
        
        self.lbl_time_rem = QLabel("Tempo restante: --", self)
        self.lbl_time_rem.setStyleSheet("color: #CBD5E1; font-weight: 600; font-size: 12px;")
        info_row.addWidget(self.lbl_time_rem)

        info_row.addStretch()

        self.lbl_stroke_count = QLabel(f"Traço: 0 / {self.total_strokes}", self)
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

        # Control Buttons
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

        # Emergency hint badge
        lbl_hint = QLabel("⚡ Pressione ESC a qualquer momento para cancelar", self)
        lbl_hint.setObjectName("BadgeWarning")
        lbl_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_hint)

    @Slot(int, int, int, float, float)
    def update_progress(self, current: int, total: int, percentage: int, elapsed_sec: float, remaining_sec: float):
        self.progress_bar.setValue(percentage)
        self.lbl_percentage.setText(f"{percentage}% concluído")
        self.lbl_stroke_count.setText(f"Traço: {current} / {total}")
        self.lbl_time_rem.setText(f"Tempo restante: {TimeEstimator.format_time(remaining_sec)}")

    def _toggle_pause(self):
        if not self.is_paused:
            self.is_paused = True
            self.lbl_title.setText("⏸️ Desenho Pausado")
            self.lbl_title.setStyleSheet("color: #FBBF24;")
            self.btn_pause.setText("▶️ CONTINUAR")
            self.btn_pause.setStyleSheet("background-color: #059669; color: white;")
            self.pause_requested.emit()
        else:
            self.is_paused = False
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
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._request_stop()
        else:
            super().keyPressEvent(event)


class CompletionDialog(QDialog):
    """
    Modal displayed upon drawing completion with stats and 'REPETIR DESENHO' / 'NOVO DESENHO' choices.
    """
    repeat_requested = Signal()

    def __init__(self, elapsed_seconds: float, quality_level: str, total_strokes: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎉 Desenho Concluído!")
        self.setFixedWidth(400)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.elapsed_seconds = elapsed_seconds
        self.quality_level = quality_level.capitalize()
        self.total_strokes = total_strokes

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

        t_str = TimeEstimator.format_time(self.elapsed_seconds)
        c_layout.addWidget(QLabel(f"⏱ <b>Tempo real utilizado:</b> {t_str}", self))
        c_layout.addWidget(QLabel(f"⭐ <b>Qualidade:</b> {self.quality_level}", self))
        c_layout.addWidget(QLabel(f"🖌️ <b>Traços realizados:</b> {self.total_strokes:,}", self))

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
        btn_repeat.clicked.connect(self._request_repeat)
        btn_layout.addWidget(btn_repeat)

        layout.addLayout(btn_layout)

    def _request_repeat(self):
        self.repeat_requested.emit()
        self.accept()
