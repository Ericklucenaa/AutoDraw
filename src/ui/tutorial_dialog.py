from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.i18n import tr
from src.ui.styles import ModernStyles

# (icon, title, text): kept as Portuguese source strings, translated on display.
STEPS = (
    (
        "🖼️",
        "Escolha uma imagem",
        "Arraste uma imagem para a janela ou clique em ESCOLHER IMAGEM. "
        "Funciona com PNG, JPG, SVG, GIF e outros formatos.",
    ),
    (
        "⚙️",
        "Ajuste o desenho",
        "Escolha a qualidade e o modo. Contorno desenha só as bordas; Preto e Branco "
        "também preenche as áreas escuras. Use as abas para ver como vai ficar.",
    ),
    (
        "🖱️",
        "Marque a área no programa de desenho",
        "Abra o Paint (ou outro programa), escolha o pincel e clique em SELECIONAR ÁREA. "
        "Depois arraste o mouse sobre a tela de desenho.",
    ),
    (
        "▶️",
        "Desenhe e não mexa no mouse",
        "Clique em DESENHAR e espere a contagem. Se você mexer no mouse, o desenho pausa; "
        "clique em CONTINUAR para seguir do mesmo ponto. ESC cancela a qualquer momento.",
    ),
)


class TutorialDialog(QDialog):
    """A four-step "how to use" walkthrough, shown on first run and from the ? button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Como usar o AutoDraw"))
        self.setFixedSize(480, 400)
        self.setStyleSheet(ModernStyles.MAIN_STYLE)
        self.index = 0
        self._init_ui()
        self._show_step()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        self.lbl_counter = QLabel(self)
        self.lbl_counter.setObjectName("StepCounter")
        layout.addWidget(self.lbl_counter)

        card = QFrame(self)
        card.setObjectName("Card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(22, 20, 22, 20)
        c_layout.setSpacing(10)
        c_layout.addStretch(1)

        self.lbl_icon = QLabel(self)
        # The global QLabel rule sets 13px; a widget-level rule beats it, setFont() does not.
        self.lbl_icon.setStyleSheet("font-size: 46px;")
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_layout.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(self)
        self.lbl_title.setStyleSheet("font-size: 19px; font-weight: bold; color: #FFFFFF;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setWordWrap(True)
        c_layout.addWidget(self.lbl_title)

        self.lbl_text = QLabel(self)
        self.lbl_text.setObjectName("HeaderSubtitle")
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("font-size: 14px; color: #CBD5E1;")
        c_layout.addWidget(self.lbl_text)
        c_layout.addStretch(1)
        layout.addWidget(card, 1)

        dots = QHBoxLayout()
        dots.addStretch()
        self.dots = []
        for _ in STEPS:
            dot = QLabel(self)
            dot.setFixedSize(10, 10)
            dots.addWidget(dot)
            self.dots.append(dot)
        dots.addStretch()
        layout.addLayout(dots)

        buttons = QHBoxLayout()
        self.btn_skip = QPushButton(tr("Pular"), self)
        self.btn_skip.clicked.connect(self.accept)
        buttons.addWidget(self.btn_skip)
        buttons.addStretch()
        self.btn_back = QPushButton(tr("◀ Anterior"), self)
        self.btn_back.clicked.connect(lambda: self._go(-1))
        buttons.addWidget(self.btn_back)
        self.btn_next = QPushButton(self)
        self.btn_next.setObjectName("PrimaryButton")
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(lambda: self._go(1))
        buttons.addWidget(self.btn_next)
        layout.addLayout(buttons)

    def _go(self, delta: int) -> None:
        target = self.index + delta
        if target >= len(STEPS):
            self.accept()
            return
        self.index = max(0, target)
        self._show_step()

    def _show_step(self) -> None:
        icon, title, text = STEPS[self.index]
        last = self.index == len(STEPS) - 1
        self.lbl_counter.setText(tr("Passo {n} de {total}", n=self.index + 1, total=len(STEPS)))
        self.lbl_icon.setText(icon)
        self.lbl_title.setText(tr(title))
        self.lbl_text.setText(tr(text))
        self.btn_back.setEnabled(self.index > 0)
        self.btn_next.setText(tr("Começar a usar ✓") if last else tr("Próximo ▶"))
        self.btn_skip.setVisible(not last)
        for i, dot in enumerate(self.dots):
            color = "#6366F1" if i == self.index else "#2A2D42"
            dot.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
