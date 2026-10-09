from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout
)

from src.config import ConfigManager
from src.logger import app_dir
from src.ui.styles import ModernStyles

QUALITY_ORDER = ("baixa", "media", "alta")
QUALITY_LABELS = ("Baixa", "Média", "Alta")
MODE_ORDER = ("contour", "bw")
MODE_LABELS = ("Contorno", "Preto e Branco")


class SettingsDialog(QDialog):
    """Settings panel for configuring AutoDraw preferences."""

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Configurações — AutoDraw")
        self.setFixedWidth(460)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_title = QLabel("⚙️ Configurações", self)
        lbl_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(lbl_title)

        layout.addWidget(self._build_general_group())
        layout.addWidget(self._build_drawing_group())
        layout.addWidget(self._build_footer())
        layout.addLayout(self._build_buttons())

    def _build_general_group(self) -> QGroupBox:
        group = QGroupBox("Geral", self)
        g_layout = QVBoxLayout(group)

        self.chk_confirm = QCheckBox("Confirmar antes de começar", self)
        self.chk_confirm.setChecked(self.config_manager.get("confirm_before_start", True))
        self.chk_confirm.setToolTip(
            "Mostra o resumo do desenho antes de assumir o mouse.\n"
            "Desmarcado automaticamente se você usar 'Não mostrar novamente'."
        )
        g_layout.addWidget(self.chk_confirm)

        self.chk_progress = QCheckBox("Mostrar janela de progresso", self)
        self.chk_progress.setChecked(self.config_manager.get("show_progress", True))
        g_layout.addWidget(self.chk_progress)

        self.chk_sound = QCheckBox("Tocar som ao terminar", self)
        self.chk_sound.setChecked(self.config_manager.get("sound_on_finish", True))
        g_layout.addWidget(self.chk_sound)

        return group

    def _build_drawing_group(self) -> QGroupBox:
        group = QGroupBox("Padrões de Desenho", self)
        d_layout = QFormLayout(group)

        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(MODE_LABELS)
        self.cmb_mode.setCurrentIndex(_index_of(MODE_ORDER, self.config_manager.get("mode", "contour"), 0))
        self.cmb_mode.setToolTip(
            "Contorno: apenas as bordas.\nPreto e Branco: bordas + preenchimento hachurado."
        )
        d_layout.addRow("Modo padrão:", self.cmb_mode)

        self.cmb_quality = QComboBox(self)
        self.cmb_quality.addItems(QUALITY_LABELS)
        self.cmb_quality.setCurrentIndex(
            _index_of(QUALITY_ORDER, str(self.config_manager.get("quality_level", "media")).lower(), 1)
        )
        d_layout.addRow("Qualidade padrão:", self.cmb_quality)

        speed_row = QHBoxLayout()
        self.slider_speed = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_speed.setRange(1, 100)
        self.slider_speed.setValue(self.config_manager.get("speed", 50))
        self.lbl_speed_value = QLabel(str(self.slider_speed.value()), self)
        self.lbl_speed_value.setFixedWidth(28)
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed_value.setText(str(v)))
        speed_row.addWidget(self.slider_speed)
        speed_row.addWidget(self.lbl_speed_value)
        d_layout.addRow("Velocidade padrão:", speed_row)

        self.spin_warn = QSpinBox(self)
        self.spin_warn.setRange(0, 100_000_000)
        self.spin_warn.setSingleStep(50_000)
        self.spin_warn.setGroupSeparatorShown(True)
        self.spin_warn.setSpecialValueText("desativado")
        self.spin_warn.setValue(int(self.config_manager.get("warn_above_points", 300_000)))
        self.spin_warn.setToolTip(
            "Avisa antes de desenhos muito longos.\n"
            "Qualidade Alta em áreas grandes passa facilmente de 1 milhão de pontos."
        )
        d_layout.addRow("Avisar acima de (pontos):", self.spin_warn)

        return group

    def _build_footer(self) -> QLabel:
        factor = self.config_manager.get("calibration_factor", 1.0)
        footer = QLabel(
            f"Calibração do estimador: ×{factor:.2f}  ·  Log: {app_dir() / 'autodraw.log'}", self
        )
        footer.setStyleSheet("color: #64748B; font-size: 11px;")
        footer.setWordWrap(True)
        return footer

    def _build_buttons(self) -> QHBoxLayout:
        btn_layout = QHBoxLayout()

        btn_reset = QPushButton("Restaurar padrões", self)
        btn_reset.setToolTip("Volta todas as opções desta janela aos valores originais.")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(btn_reset)

        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Salvar", self)
        btn_save.setObjectName("PrimaryButton")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save_and_close)
        btn_layout.addWidget(btn_save)

        return btn_layout

    def _reset_defaults(self):
        from src.config import DEFAULT_CONFIG

        self.chk_confirm.setChecked(DEFAULT_CONFIG["confirm_before_start"])
        self.chk_progress.setChecked(DEFAULT_CONFIG["show_progress"])
        self.chk_sound.setChecked(DEFAULT_CONFIG["sound_on_finish"])
        self.cmb_mode.setCurrentIndex(_index_of(MODE_ORDER, DEFAULT_CONFIG["mode"], 0))
        self.cmb_quality.setCurrentIndex(_index_of(QUALITY_ORDER, DEFAULT_CONFIG["quality_level"], 1))
        self.slider_speed.setValue(DEFAULT_CONFIG["speed"])
        self.spin_warn.setValue(DEFAULT_CONFIG["warn_above_points"])

    def _save_and_close(self):
        # One disk write for the whole dialog instead of one per field.
        self.config_manager.set_many({
            "confirm_before_start": self.chk_confirm.isChecked(),
            "show_progress": self.chk_progress.isChecked(),
            "sound_on_finish": self.chk_sound.isChecked(),
            "mode": MODE_ORDER[self.cmb_mode.currentIndex()],
            "quality_level": QUALITY_ORDER[self.cmb_quality.currentIndex()],
            "speed": self.slider_speed.value(),
            "warn_above_points": self.spin_warn.value(),
        })
        self.accept()


def _index_of(values, needle, fallback: int) -> int:
    try:
        return values.index(needle)
    except ValueError:
        return fallback
