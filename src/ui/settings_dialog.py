from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QSlider, QPushButton, QGroupBox, QFormLayout
)

from src.config import ConfigManager
from src.ui.styles import ModernStyles


class SettingsDialog(QDialog):
    """Minimal settings panel for configuring AutoDraw preferences."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Configurações — AutoDraw")
        self.setFixedWidth(420)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Title
        lbl_title = QLabel("⚙️ Configurações", self)
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(lbl_title)

        # 1. Geral Group
        group_general = QGroupBox("Geral", self)
        group_general.setStyleSheet("QGroupBox { color: #A5B4FC; font-weight: bold; border: 1px solid #2A2D42; border-radius: 8px; margin-top: 10px; padding-top: 10px; }")
        g_layout = QVBoxLayout(group_general)

        self.chk_confirm = QCheckBox("Confirmar antes de começar", self)
        self.chk_confirm.setChecked(self.config_manager.get("confirm_before_start", True))
        g_layout.addWidget(self.chk_confirm)

        self.chk_progress = QCheckBox("Mostrar janela de progresso", self)
        self.chk_progress.setChecked(self.config_manager.get("show_progress", True))
        g_layout.addWidget(self.chk_progress)

        self.chk_sound = QCheckBox("Tocar som ao terminar", self)
        self.chk_sound.setChecked(self.config_manager.get("sound_on_finish", True))
        g_layout.addWidget(self.chk_sound)

        layout.addWidget(group_general)

        # 2. Desenho Group
        group_drawing = QGroupBox("Padrões de Desenho", self)
        group_drawing.setStyleSheet("QGroupBox { color: #A5B4FC; font-weight: bold; border: 1px solid #2A2D42; border-radius: 8px; margin-top: 10px; padding-top: 10px; }")
        d_layout = QFormLayout(group_drawing)

        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(["Contorno", "Preto e Branco"])
        curr_mode = self.config_manager.get("mode", "contour")
        self.cmb_mode.setCurrentIndex(0 if curr_mode == "contour" else 1)
        d_layout.addRow("Modo padrão:", self.cmb_mode)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_speed.setRange(1, 100)
        self.slider_speed.setValue(self.config_manager.get("speed", 50))
        d_layout.addRow("Velocidade padrão:", self.slider_speed)

        self.slider_quality = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_quality.setRange(1, 100)
        self.slider_quality.setValue(self.config_manager.get("quality", 50))
        d_layout.addRow("Qualidade padrão:", self.slider_quality)

        layout.addWidget(group_drawing)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Salvar", self)
        btn_save.setObjectName("PrimaryButton")
        btn_save.clicked.connect(self._save_and_close)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _save_and_close(self):
        self.config_manager.set("confirm_before_start", self.chk_confirm.isChecked())
        self.config_manager.set("show_progress", self.chk_progress.isChecked())
        self.config_manager.set("sound_on_finish", self.chk_sound.isChecked())
        
        mode = "contour" if self.cmb_mode.currentIndex() == 0 else "bw"
        self.config_manager.set("mode", mode)
        self.config_manager.set("speed", self.slider_speed.value())
        self.config_manager.set("quality", self.slider_quality.value())

        self.accept()
