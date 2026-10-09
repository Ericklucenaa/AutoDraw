from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
)

from src.time_estimator import TimeEstimator
from src.ui.styles import ModernStyles

QUALITY_LABELS = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}


class ConfirmationDialog(QDialog):
    """
    Summary modal presented before drawing starts.
    Contains summary details, ESC safety warning, and 'Não mostrar novamente' option.
    """

    def __init__(
        self,
        filename: str,
        img_w: int,
        img_h: int,
        quality_level: str,
        mode: str,
        area_w: int,
        area_h: int,
        total_strokes: int,
        total_points: int,
        estimated_sec: float,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Confirmar Desenho — AutoDraw")
        self.setFixedWidth(460)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.filename = filename
        self.img_w = img_w
        self.img_h = img_h
        self.quality_level = QUALITY_LABELS.get(quality_level.lower(), quality_level.capitalize())
        self.mode_label = "Preto e Branco" if mode == "bw" else "Contorno"
        self.area_w = area_w
        self.area_h = area_h
        self.total_strokes = total_strokes
        self.total_points = total_points
        self.estimated_sec = estimated_sec

        self.skip_future: bool = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel("🎨 Seu desenho está pronto!", self)
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #6366F1;")
        layout.addWidget(lbl_title)

        card = QFrame(self)
        card.setObjectName("Card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(8)

        t_str = TimeEstimator.format_time(self.estimated_sec)
        for line in (
            f"📄 <b>Imagem:</b> {self.filename}",
            f"📏 <b>Resolução:</b> {self.img_w} × {self.img_h} px",
            f"⭐ <b>Qualidade:</b> {self.quality_level} &nbsp;·&nbsp; <b>Modo:</b> {self.mode_label}",
            f"📍 <b>Área Selecionada:</b> {self.area_w} × {self.area_h} px",
            f"🖌️ <b>Traços:</b> {self.total_strokes:,} &nbsp;·&nbsp; <b>Pontos:</b> {self.total_points:,}",
            f"⏱ <b>Tempo estimado:</b> ≈ {t_str}",
        ):
            c_layout.addWidget(QLabel(line, self))

        layout.addWidget(card)

        warn_card = QFrame(self)
        warn_card.setObjectName("Card")
        w_layout = QVBoxLayout(warn_card)
        w_layout.setContentsMargins(12, 10, 12, 10)

        lbl_w1 = QLabel("⚠️ O AutoDraw assumirá o controle do mouse para desenhar.", self)
        lbl_w1.setStyleSheet("color: #FBBF24; font-weight: bold;")
        lbl_w2 = QLabel("Certifique-se de que o programa de desenho esteja aberto na área selecionada.", self)
        lbl_w2.setWordWrap(True)
        lbl_w3 = QLabel("⚡ Pressione ESC a qualquer momento para cancelar.", self)
        lbl_w3.setStyleSheet("color: #EF4444; font-weight: bold;")

        w_layout.addWidget(lbl_w1)
        w_layout.addWidget(lbl_w2)
        w_layout.addWidget(lbl_w3)
        layout.addWidget(warn_card)

        self.chk_skip = QCheckBox("Não mostrar esta confirmação novamente", self)
        self.chk_skip.setToolTip("Você pode reativá-la depois em ⚙️ Configurações.")
        layout.addWidget(self.chk_skip)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("CANCELAR", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_start = QPushButton("▶ COMEÇAR", self)
        btn_start.setObjectName("PrimaryButton")
        btn_start.setDefault(True)
        btn_start.clicked.connect(self._on_start)
        btn_layout.addWidget(btn_start)

        layout.addLayout(btn_layout)

    def _on_start(self):
        self.skip_future = self.chk_skip.isChecked()
        self.accept()


class CountdownOverlayDialog(QDialog):
    """3-second countdown dialog before mouse control begins."""

    def __init__(self, countdown_sec: int = 3, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prepare o programa de desenho...")
        self.setFixedSize(360, 240)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self.count = max(1, countdown_sec)
        self._init_ui()

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_head = QLabel("Prepare o programa de desenho...", self)
        self.lbl_head.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_head.setStyleSheet("color: #A5B4FC;")
        self.lbl_head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_head.setWordWrap(True)
        layout.addWidget(self.lbl_head)

        self.lbl_num = QLabel(str(self.count), self)
        self.lbl_num.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        self.lbl_num.setStyleSheet("color: #4ADE80;")
        self.lbl_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_num)

        lbl_sub = QLabel("O controle do mouse iniciará em breve\n[ ESC cancela ]", self)
        lbl_sub.setStyleSheet("color: #94A3B8; font-size: 12px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_sub)

    def _tick(self):
        self.count -= 1
        if self.count > 0:
            self.lbl_num.setText(str(self.count))
            return
        self.timer.stop()
        self.lbl_num.setText("Começando!")
        QTimer.singleShot(400, self.accept)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.timer.stop()
            self.reject()
        else:
            super().keyPressEvent(event)
