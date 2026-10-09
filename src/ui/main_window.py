from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QRadioButton, QScrollArea,
    QSlider, QVBoxLayout, QWidget
)

from src.async_processor import ImageProcessorWorker
from src.config import ConfigManager
from src.drawing_engine import DrawingEngineWorker
from src.image_loader import SUPPORTED_LABEL, ImageInfo, ImageLoader
from src.logger import get_logger
from src.time_estimator import TimeEstimator
from src.ui.confirmation_dialog import ConfirmationDialog, CountdownOverlayDialog
from src.ui.drawing_dialog import CompletionDialog, DrawingProgressDialog
from src.ui.overlay_widget import AreaSelectionOverlay
from src.ui.settings_dialog import SettingsDialog
from src.ui.styles import ModernStyles, apply_object_name
from src.ui.widgets import ImagePreviewCanvas, RecentImagesBar

log = get_logger("ui.main")

Stroke = List[Tuple[int, int]]

QUALITY_ORDER = ("baixa", "media", "alta")
QUALITY_LABELS = {"baixa": "Baixa", "media": "Média", "alta": "Alta"}
MODE_ORDER = ("contour", "bw")

# Reprocessing is expensive, so geometry changes are coalesced; dragging the
# speed slider used to spawn one full OpenCV pass per pixel of travel.
RECALC_DEBOUNCE_MS = 250
SETTINGS_SAVE_DEBOUNCE_MS = 800
COUNTDOWN_SECONDS = 3


class MainWindow(QMainWindow):
    """Main Application Window for AutoDraw."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoDraw — Desenhista Automático")
        self.setMinimumSize(560, 800)
        self.resize(600, 880)

        self.config_manager = ConfigManager()
        self.setStyleSheet(ModernStyles.MAIN_STYLE)
        self.setAcceptDrops(True)  # Enable Drag & Drop for image files

        self.current_image_info: Optional[ImageInfo] = None
        self.selected_area: Optional[Dict[str, int]] = self.config_manager.get("last_area")
        self.processed_strokes: List[Stroke] = []
        self.estimated_seconds: float = 0.0
        self.total_points: int = 0

        self.processor_worker: Optional[ImageProcessorWorker] = None
        self.drawing_worker: Optional[DrawingEngineWorker] = None
        self.progress_dialog: Optional[DrawingProgressDialog] = None
        self.overlay: Optional[AreaSelectionOverlay] = None

        self._request_counter = 0
        self._active_request_id = -1

        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.setInterval(RECALC_DEBOUNCE_MS)
        self._recalc_timer.timeout.connect(self._start_processing)

        self._settings_save_timer = QTimer(self)
        self._settings_save_timer.setSingleShot(True)
        self._settings_save_timer.setInterval(SETTINGS_SAVE_DEBOUNCE_MS)
        self._settings_save_timer.timeout.connect(self._persist_drawing_settings)

        self._init_ui()
        self._load_saved_defaults()

    # ---------------- construction ----------------

    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(14)

        for card in (
            self._build_header_card(),
            self._build_image_card(),
            self._build_options_card(),
            self._build_area_card(),
            self._build_action_card(),
            self._build_footer_badge(),
        ):
            scroll_layout.addWidget(card)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    def _build_header_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)

        titles = QVBoxLayout()
        lbl_title = QLabel("🎨 AutoDraw", self)
        lbl_title.setObjectName("HeaderTitle")
        lbl_subtitle = QLabel("Transforme qualquer imagem em traços automáticos.", self)
        lbl_subtitle.setObjectName("HeaderSubtitle")
        titles.addWidget(lbl_title)
        titles.addWidget(lbl_subtitle)
        layout.addLayout(titles)
        layout.addStretch()

        btn_settings = QPushButton("⚙️", self)
        btn_settings.setFixedSize(38, 38)
        btn_settings.setToolTip("Configurações")
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        return card

    def _build_image_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        self.btn_choose_image = QPushButton("📁 ESCOLHER IMAGEM", self)
        self.btn_choose_image.setFixedHeight(38)
        self.btn_choose_image.clicked.connect(self._choose_image_dialog)
        top_row.addWidget(self.btn_choose_image)

        self.lbl_image_info = QLabel("Nenhuma imagem selecionada", self)
        self.lbl_image_info.setObjectName("Badge")
        top_row.addWidget(self.lbl_image_info)
        top_row.addStretch()
        layout.addLayout(top_row)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self.preview_tabs: Dict[str, QPushButton] = {}
        for mode, text in (
            ("processed", "🎨 Resultado Processado"),
            ("original", "🖼️ Imagem Original"),
            ("area", "📐 Simulação no Paint"),
        ):
            button = QPushButton(text, self)
            button.setObjectName("TabButton")
            button.setCheckable(True)
            button.setChecked(mode == "processed")
            button.clicked.connect(lambda _=False, m=mode: self._set_preview_mode(m))
            tab_row.addWidget(button)
            self.preview_tabs[mode] = button
        tab_row.addStretch()
        layout.addLayout(tab_row)

        self.preview_canvas = ImagePreviewCanvas(self)
        layout.addWidget(self.preview_canvas)

        self.recent_bar = RecentImagesBar(self)
        self.recent_bar.image_selected.connect(self._load_image_from_path)
        layout.addWidget(self.recent_bar)

        return card

    def _build_options_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        lbl_title = QLabel("⚙️ Configuração do Desenho", self)
        lbl_title.setObjectName("SectionTitle")
        layout.addWidget(lbl_title)

        # Quality + mode
        quality_row = QHBoxLayout()
        lbl_quality = QLabel("Qualidade:", self)
        lbl_quality.setStyleSheet("font-weight: 600;")
        quality_row.addWidget(lbl_quality)

        self.cmb_quality = QComboBox(self)
        self.cmb_quality.addItems(["Baixa", "Média", "Alta"])
        self.cmb_quality.setCurrentIndex(1)
        self.cmb_quality.currentIndexChanged.connect(self._on_geometry_option_changed)
        quality_row.addWidget(self.cmb_quality)

        lbl_mode = QLabel("Modo:", self)
        lbl_mode.setStyleSheet("font-weight: 600;")
        quality_row.addWidget(lbl_mode)

        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems(["Contorno", "Preto e Branco"])
        self.cmb_mode.setToolTip(
            "Contorno: apenas as bordas da imagem.\n"
            "Preto e Branco: bordas mais preenchimento hachurado das áreas escuras."
        )
        self.cmb_mode.currentIndexChanged.connect(self._on_geometry_option_changed)
        quality_row.addWidget(self.cmb_mode)

        quality_row.addStretch()
        layout.addLayout(quality_row)

        # Aspect ratio
        aspect_row = QHBoxLayout()
        lbl_aspect = QLabel("Ajuste da Imagem:", self)
        lbl_aspect.setStyleSheet("font-weight: 600;")
        aspect_row.addWidget(lbl_aspect)

        self.btn_group_aspect = QButtonGroup(self)
        self.radio_aspect_keep = QRadioButton("Manter proporção", self)
        self.radio_aspect_fill = QRadioButton("Preencher área", self)
        self.radio_aspect_stretch = QRadioButton("Esticar", self)
        for index, radio in enumerate(
            (self.radio_aspect_keep, self.radio_aspect_fill, self.radio_aspect_stretch)
        ):
            self.btn_group_aspect.addButton(radio, index)
            aspect_row.addWidget(radio)
        aspect_row.addStretch()
        layout.addLayout(aspect_row)
        self.btn_group_aspect.idClicked.connect(self._on_geometry_option_changed)

        # Speed
        speed_row = QHBoxLayout()
        lbl_speed = QLabel("Velocidade:", self)
        lbl_speed.setStyleSheet("font-weight: 600;")
        speed_row.addWidget(lbl_speed)

        lbl_slow = QLabel("Lento", self)
        lbl_slow.setStyleSheet("color: #64748B; font-size: 11px;")
        speed_row.addWidget(lbl_slow)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_speed.setRange(1, 100)
        self.slider_speed.setValue(50)
        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        speed_row.addWidget(self.slider_speed)

        lbl_fast = QLabel("Rápido", self)
        lbl_fast.setStyleSheet("color: #64748B; font-size: 11px;")
        speed_row.addWidget(lbl_fast)
        layout.addLayout(speed_row)

        self.chk_simplify = QCheckBox("Simplificar imagem (remover ruídos pequenos)", self)
        self.chk_simplify.toggled.connect(self._on_geometry_option_changed)
        layout.addWidget(self.chk_simplify)

        return card

    def _build_area_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.btn_select_area = QPushButton("🖱️ SELECIONAR ÁREA DE DESENHO", self)
        self.btn_select_area.setFixedHeight(42)
        self.btn_select_area.clicked.connect(self._start_area_selection)
        layout.addWidget(self.btn_select_area)

        self.lbl_area_status = QLabel("Área: ❌ Não selecionada", self)
        self.lbl_area_status.setObjectName("BadgeWarning")
        layout.addWidget(self.lbl_area_status)

        return card

    def _build_action_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.lbl_estimated_time = QLabel("⏱ Tempo estimado: --", self)
        self.lbl_estimated_time.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_estimated_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_estimated_time.setStyleSheet("color: #4ADE80;")
        layout.addWidget(self.lbl_estimated_time)

        self.lbl_trajectory_summary = QLabel("Aguardando seleção de imagem e área...", self)
        self.lbl_trajectory_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_trajectory_summary.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(self.lbl_trajectory_summary)

        self.lbl_volume_warning = QLabel("", self)
        self.lbl_volume_warning.setObjectName("BadgeDanger")
        self.lbl_volume_warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_volume_warning.setWordWrap(True)
        self.lbl_volume_warning.setVisible(False)
        layout.addWidget(self.lbl_volume_warning)

        self.btn_draw = QPushButton("▶ DESENHAR", self)
        self.btn_draw.setObjectName("PrimaryButton")
        self.btn_draw.setFixedHeight(50)
        self.btn_draw.setEnabled(False)
        self.btn_draw.clicked.connect(self._start_drawing_process)
        layout.addWidget(self.btn_draw)

        return card

    def _build_footer_badge(self) -> QLabel:
        badge = QLabel("⚡ Pressione ESC a qualquer momento para cancelar o desenho", self)
        badge.setObjectName("BadgeWarning")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return badge

    # ---------------- drag & drop ----------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._first_supported_url(event) is not None:
            event.acceptProposedAction()
            self.preview_canvas.set_drag_hover(True)
            return
        self.preview_canvas.set_drag_hover(False)
        event.ignore()

    def dragLeaveEvent(self, event):
        self.preview_canvas.set_drag_hover(False)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self.preview_canvas.set_drag_hover(False)
        filepath = self._first_supported_url(event)

        if filepath is None:
            if event.mimeData().hasUrls():
                QMessageBox.warning(
                    self,
                    "Formato não suportado",
                    f"❌ Formato de imagem não suportado.\n\nAceitos: {SUPPORTED_LABEL}",
                )
            event.ignore()
            return

        self._load_image_from_path(filepath)
        event.acceptProposedAction()

    @staticmethod
    def _first_supported_url(event) -> Optional[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            filepath = url.toLocalFile()
            if ImageLoader.is_supported(filepath):
                return filepath
        return None

    # ---------------- state restore ----------------

    def _load_saved_defaults(self):
        self.recent_bar.set_recent_files(self.config_manager.get("recent_images", []))

        widgets = (
            self.cmb_quality, self.cmb_mode, self.slider_speed, self.chk_simplify,
            self.radio_aspect_keep, self.radio_aspect_fill, self.radio_aspect_stretch,
        )
        # Restoring values must not look like user edits, or every widget would
        # queue another reprocessing pass.
        for widget in widgets:
            widget.blockSignals(True)
        try:
            quality = str(self.config_manager.get("quality_level", "media")).lower()
            self.cmb_quality.setCurrentIndex(
                QUALITY_ORDER.index(quality) if quality in QUALITY_ORDER else 1
            )
            mode = self.config_manager.get("mode", "contour")
            self.cmb_mode.setCurrentIndex(MODE_ORDER.index(mode) if mode in MODE_ORDER else 0)

            aspect = self.config_manager.get("aspect_mode", "keep_aspect")
            {"fill": self.radio_aspect_fill, "stretch": self.radio_aspect_stretch}.get(
                aspect, self.radio_aspect_keep
            ).setChecked(True)

            self.slider_speed.setValue(int(self.config_manager.get("speed", 50)))
            self.chk_simplify.setChecked(bool(self.config_manager.get("simplify_image", False)))
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._update_area_label()
        self._update_draw_button_state()

    def _update_area_label(self):
        area = self.selected_area
        if not area or area.get("w", 0) <= 0 or area.get("h", 0) <= 0:
            self.lbl_area_status.setText("Área: ❌ Não selecionada")
            apply_object_name(self.lbl_area_status, "BadgeWarning")
            return
        self.lbl_area_status.setText(
            f"Área: {area['w']}×{area['h']} px em ({area['x']}, {area['y']})"
        )
        apply_object_name(self.lbl_area_status, "BadgeSuccess")

    # ---------------- image loading ----------------

    def _choose_image_dialog(self):
        file_filter = (
            "Imagens Suportadas (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.svg *.tif *.tiff);;"
            "Todos os arquivos (*.*)"
        )
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Escolher imagem para AutoDraw", "", file_filter
        )
        if filepath:
            self._load_image_from_path(filepath)

    def _load_image_from_path(self, filepath: str):
        info, error = ImageLoader.try_load_image(filepath)
        if info is None:
            # Previously a failed load did nothing at all, leaving the user
            # staring at an unchanged window with no explanation.
            QMessageBox.critical(self, "Não foi possível abrir a imagem", error or "Erro desconhecido.")
            return

        self.current_image_info = info
        self.config_manager.add_recent_image(filepath)
        self.recent_bar.set_recent_files(self.config_manager.get("recent_images", []))

        self.lbl_image_info.setText(f"{info.filename} — {info.width} × {info.height} px")
        apply_object_name(self.lbl_image_info, "BadgeSuccess")

        self.preview_canvas.set_image(info.cv_image)
        self.preview_canvas.clear_vector_paths()
        self._invalidate_strokes()
        self._schedule_recalculation()

    # ---------------- area selection ----------------

    def _start_area_selection(self):
        self.hide()
        self.overlay = AreaSelectionOverlay()
        self.overlay.area_selected.connect(self._on_area_selected)
        self.overlay.cancelled.connect(self._on_area_selection_cancelled)
        self.overlay.show()

    @Slot(int, int, int, int)
    def _on_area_selected(self, x: int, y: int, w: int, h: int):
        self.selected_area = {"x": x, "y": y, "w": w, "h": h}
        self.config_manager.set("last_area", self.selected_area)
        log.info("Area selected: %dx%d at (%d, %d)", w, h, x, y)

        self._update_area_label()
        self._restore_window()
        self._invalidate_strokes()
        self._schedule_recalculation()

    @Slot()
    def _on_area_selection_cancelled(self):
        self._restore_window()

    def _restore_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    # ---------------- option changes ----------------

    def _current_quality(self) -> str:
        return QUALITY_ORDER[max(0, min(2, self.cmb_quality.currentIndex()))]

    def _current_mode(self) -> str:
        return MODE_ORDER[max(0, min(1, self.cmb_mode.currentIndex()))]

    def _current_aspect_mode(self) -> str:
        if self.radio_aspect_fill.isChecked():
            return "fill"
        if self.radio_aspect_stretch.isChecked():
            return "stretch"
        return "keep_aspect"

    def _on_geometry_option_changed(self, *_):
        """Quality, mode, aspect or simplification changed: geometry must be redone."""
        self._invalidate_strokes()
        self._schedule_recalculation()
        self._settings_save_timer.start()

    def _on_speed_changed(self, *_):
        """
        Speed changed: only the time estimate moves, so skip reprocessing.

        Speed does not affect a single coordinate, yet it used to re-run the
        whole Canny/trace/optimize pipeline on every slider tick.
        """
        if self.processed_strokes:
            self.estimated_seconds = TimeEstimator.estimate_seconds(
                strokes=self.processed_strokes,
                speed=self.slider_speed.value(),
                calibration_factor=self.config_manager.get("calibration_factor", 1.0),
            )
            self._update_estimate_labels()
        self._settings_save_timer.start()

    def _persist_drawing_settings(self):
        self.config_manager.set_many({
            "quality_level": self._current_quality(),
            "mode": self._current_mode(),
            "aspect_mode": self._current_aspect_mode(),
            "speed": self.slider_speed.value(),
            "simplify_image": self.chk_simplify.isChecked(),
        })

    def _invalidate_strokes(self):
        self.processed_strokes = []
        self.total_points = 0
        self.estimated_seconds = 0.0
        self.lbl_volume_warning.setVisible(False)
        self._update_draw_button_state()

    # ---------------- processing ----------------

    def _schedule_recalculation(self):
        if not self.current_image_info or not self.selected_area:
            return
        self.lbl_estimated_time.setText("⏱ Analisando imagem...")
        self.lbl_trajectory_summary.setText("Calculando trajetórias...")
        self._recalc_timer.start()

    def _start_processing(self):
        if not self.current_image_info or not self.selected_area:
            return

        self._cancel_processing()
        self._request_counter += 1
        self._active_request_id = self._request_counter

        worker = ImageProcessorWorker(
            cv_img=self.current_image_info.cv_image,
            target_w=self.selected_area["w"],
            target_h=self.selected_area["h"],
            mode=self._current_mode(),
            aspect_mode=self._current_aspect_mode(),
            quality_level=self._current_quality(),
            simplify_image=self.chk_simplify.isChecked(),
            speed=self.slider_speed.value(),
            calibration_factor=self.config_manager.get("calibration_factor", 1.0),
            request_id=self._active_request_id,
            parent=self,
        )
        worker.processing_finished.connect(self._on_processing_finished)
        worker.processing_error.connect(self._on_processing_error)
        worker.processing_cancelled.connect(self._on_processing_cancelled)
        worker.finished.connect(lambda w=worker: self._release_processor_worker(w))

        self.processor_worker = worker
        worker.start()

    def _release_processor_worker(self, worker: ImageProcessorWorker) -> None:
        """
        Drops the reference before the C++ object goes away.

        deleteLater() destroys the underlying QThread, so a still-held Python
        wrapper raises RuntimeError on the next isRunning() call.
        """
        if self.processor_worker is worker:
            self.processor_worker = None
        worker.deleteLater()

    def _cancel_processing(self):
        """
        Asks a running processing pass to stop and stops tracking it.

        The old code called QThread.terminate(), which can kill the thread in
        the middle of an OpenCV allocation; and because results were accepted
        unconditionally, a slow earlier pass could overwrite a newer one.
        """
        worker = self.processor_worker
        self.processor_worker = None
        if worker is None:
            return
        try:
            if worker.isRunning():
                worker.cancel()
        except RuntimeError:
            pass  # already destroyed by Qt

    def _is_stale(self, request_id: int) -> bool:
        return request_id != self._active_request_id

    @Slot(list, float, int, int)
    def _on_processing_finished(self, strokes: list, est_seconds: float, total_pts: int, request_id: int):
        if self._is_stale(request_id):
            return

        self.processed_strokes = strokes
        self.estimated_seconds = est_seconds
        self.total_points = total_pts

        area = self.selected_area or {"w": 0, "h": 0}
        self.preview_canvas.set_vector_paths(strokes, area.get("w", 0), area.get("h", 0))

        self._update_estimate_labels()
        self._update_draw_button_state()

    @Slot(str, int)
    def _on_processing_error(self, message: str, request_id: int):
        if self._is_stale(request_id):
            return
        log.error("Processing failed: %s", message)
        self.lbl_estimated_time.setText("⏱ Tempo estimado: --")
        self.lbl_trajectory_summary.setText("❌ Falha ao processar a imagem.")
        self._invalidate_strokes()
        QMessageBox.critical(
            self, "Erro ao processar", f"Não foi possível processar a imagem:\n\n{message}"
        )

    @Slot(int)
    def _on_processing_cancelled(self, request_id: int):
        log.debug("Processing request %d cancelled", request_id)

    def _update_estimate_labels(self):
        self.lbl_estimated_time.setText(
            f"⏱ Tempo estimado: ≈ {TimeEstimator.format_time(self.estimated_seconds)}"
        )
        self.lbl_trajectory_summary.setText(
            f"Traços: {len(self.processed_strokes):,} | Pontos: {self.total_points:,} | "
            f"Qualidade: {QUALITY_LABELS[self._current_quality()]}"
        )

        threshold = int(self.config_manager.get("warn_above_points", 300_000))
        over_budget = bool(threshold) and self.total_points > threshold
        self.lbl_volume_warning.setVisible(over_budget)
        if over_budget:
            self.lbl_volume_warning.setText(
                f"⚠️ Desenho muito longo: {self.total_points:,} pontos "
                f"(≈ {TimeEstimator.format_time(self.estimated_seconds)}). "
                "Reduza a qualidade ou a área para terminar mais rápido."
            )

    def _update_draw_button_state(self):
        self.btn_draw.setEnabled(
            self.current_image_info is not None
            and self.selected_area is not None
            and bool(self.processed_strokes)
        )

    # ---------------- settings ----------------

    def _open_settings(self):
        dialog = SettingsDialog(self.config_manager, self)
        if not dialog.exec():
            return
        self._load_saved_defaults()
        self._invalidate_strokes()
        self._schedule_recalculation()

    # ---------------- drawing ----------------

    def _start_drawing_process(self):
        if not self.current_image_info or not self.selected_area or not self.processed_strokes:
            QMessageBox.warning(
                self, "Aviso", "Por favor, selecione uma imagem e uma área de desenho."
            )
            return

        if self.config_manager.get("confirm_before_start", True):
            dialog = ConfirmationDialog(
                filename=self.current_image_info.filename,
                img_w=self.current_image_info.width,
                img_h=self.current_image_info.height,
                quality_level=self._current_quality(),
                mode=self._current_mode(),
                area_w=self.selected_area["w"],
                area_h=self.selected_area["h"],
                total_strokes=len(self.processed_strokes),
                total_points=self.total_points,
                estimated_sec=self.estimated_seconds,
                parent=self,
            )
            if not dialog.exec():
                return
            if dialog.skip_future:
                self.config_manager.set("confirm_before_start", False)

        if not self._confirm_long_drawing():
            return

        self._run_countdown_then_draw()

    def _confirm_long_drawing(self) -> bool:
        threshold = int(self.config_manager.get("warn_above_points", 300_000))
        if not threshold or self.total_points <= threshold:
            return True

        answer = QMessageBox.question(
            self,
            "Desenho muito longo",
            f"Este desenho tem {self.total_points:,} pontos e deve levar cerca de "
            f"{TimeEstimator.format_time(self.estimated_seconds)}.\n\n"
            "O mouse ficará ocupado todo esse tempo. Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _run_countdown_then_draw(self):
        countdown = CountdownOverlayDialog(countdown_sec=COUNTDOWN_SECONDS, parent=self)
        if countdown.exec():
            self._execute_drawing()

    def _execute_drawing(self):
        if self.drawing_worker is not None and self.drawing_worker.isRunning():
            return

        worker = DrawingEngineWorker(
            strokes=self.processed_strokes,
            start_x=self.selected_area["x"],
            start_y=self.selected_area["y"],
            speed=self.slider_speed.value(),
            estimated_total_seconds=self.estimated_seconds,
            parent=self,
        )

        dialog = DrawingProgressDialog(
            total_strokes=len(self.processed_strokes),
            estimated_total_sec=self.estimated_seconds,
            sound_on_finish=self.config_manager.get("sound_on_finish", True),
            parent=self,
        )

        worker.progress_changed.connect(dialog.update_progress)
        worker.drawing_finished.connect(self._on_drawing_finished)
        worker.drawing_cancelled.connect(self._on_drawing_cancelled)
        worker.drawing_error.connect(self._on_drawing_error)

        dialog.pause_requested.connect(worker.pause)
        dialog.resume_requested.connect(worker.resume)
        dialog.stop_requested.connect(worker.stop)
        worker.finished.connect(lambda w=worker, d=dialog: self._release_drawing_worker(w, d))

        self.drawing_worker = worker
        self.progress_dialog = dialog

        worker.start()
        if self.config_manager.get("show_progress", True):
            dialog.exec()

    def _release_drawing_worker(self, worker: DrawingEngineWorker, dialog: DrawingProgressDialog) -> None:
        """Clears the worker and its dialog so repeats do not accumulate them."""
        if self.drawing_worker is worker:
            self.drawing_worker = None
        if self.progress_dialog is dialog:
            self.progress_dialog = None
        worker.deleteLater()
        dialog.deleteLater()

    @Slot(float, int, int)
    def _on_drawing_finished(self, actual_elapsed: float, total_strokes: int, total_pts: int):
        if self.progress_dialog is not None:
            self.progress_dialog.on_finished()

        self.config_manager.set(
            "calibration_factor",
            TimeEstimator.calibrate(
                current_factor=self.config_manager.get("calibration_factor", 1.0),
                estimated_seconds=self.estimated_seconds,
                actual_seconds=actual_elapsed,
            ),
        )

        # Deferred so the completion dialog opens on the main event loop rather
        # than nested inside the progress dialog's exec().
        QTimer.singleShot(
            0, lambda: self._show_completion(actual_elapsed, total_strokes, total_pts)
        )

    def _show_completion(self, elapsed: float, total_strokes: int, total_pts: int):
        dialog = CompletionDialog(
            elapsed_seconds=elapsed,
            quality_level=self._current_quality(),
            total_strokes=total_strokes,
            total_points=total_pts,
            parent=self,
        )
        dialog.exec()
        if dialog.repeat_chosen:
            # Repeating goes through the countdown again: the mouse should
            # never be taken over without warning.
            QTimer.singleShot(0, self._run_countdown_then_draw)

    @Slot(str)
    def _on_drawing_cancelled(self, reason: str):
        if self.progress_dialog is not None:
            self.progress_dialog.reject()
        QMessageBox.warning(self, "Cancelado", f"O desenho foi cancelado: {reason}")

    @Slot(str)
    def _on_drawing_error(self, err_msg: str):
        if self.progress_dialog is not None:
            self.progress_dialog.reject()
        QMessageBox.critical(self, "Erro", f"Ocorreu um erro durante o desenho:\n{err_msg}")

    # ---------------- preview tabs & teardown ----------------

    def _set_preview_mode(self, mode: str):
        for name, button in self.preview_tabs.items():
            button.setChecked(name == mode)
        self.preview_canvas.set_view_mode(mode)

    def closeEvent(self, event):
        """
        Stops every worker before the window goes away.

        Without this, closing the window mid-drawing left the QThread running
        with the left mouse button held down, so the pointer kept painting in
        whatever application was in front.
        """
        if self._settings_save_timer.isActive():
            self._settings_save_timer.stop()
            self._persist_drawing_settings()

        self._recalc_timer.stop()
        self._cancel_processing()

        worker = self.drawing_worker
        self.drawing_worker = None
        try:
            if worker is not None and worker.isRunning():
                log.info("Window closing while drawing: stopping worker")
                worker.stop()
                if not worker.wait(3000):
                    log.warning("Drawing worker did not stop in time")
                worker.mouse.safe_reset()
        except RuntimeError:
            pass  # already destroyed by Qt

        if self.overlay is not None:
            self.overlay.close()

        super().closeEvent(event)
