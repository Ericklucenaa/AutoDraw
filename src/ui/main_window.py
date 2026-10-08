import os
from typing import Optional, Dict, Any, List, Tuple
from PySide6.QtCore import Qt, Slot, QTimer, QUrl
from PySide6.QtGui import QFont, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QRadioButton, QButtonGroup, QSlider, QCheckBox,
    QMessageBox, QScrollArea, QComboBox
)

from src.config import ConfigManager
from src.image_loader import ImageLoader, ImageInfo, SUPPORTED_EXTENSIONS
from src.image_processor import ImageProcessor
from src.time_estimator import TimeEstimator
from src.async_processor import ImageProcessorWorker
from src.drawing_engine import DrawingEngineWorker
from src.ui.styles import ModernStyles
from src.ui.widgets import ImagePreviewCanvas, RecentImagesBar
from src.ui.overlay_widget import AreaSelectionOverlay
from src.ui.drawing_dialog import DrawingProgressDialog, CompletionDialog
from src.ui.confirmation_dialog import ConfirmationDialog, CountdownOverlayDialog
from src.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main Application Window for AutoDraw V2."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoDraw — Desenhista Automático")
        self.setMinimumSize(560, 800)
        self.resize(600, 860)

        self.config_manager = ConfigManager()
        self.setStyleSheet(ModernStyles.MAIN_STYLE)
        self.setAcceptDrops(True)  # Enable Drag & Drop for image files!

        self.current_image_info: Optional[ImageInfo] = None
        self.selected_area: Optional[Dict[str, int]] = self.config_manager.get("last_area")
        self.processed_strokes: List[List[Tuple[int, int]]] = []
        self.estimated_seconds: float = 0.0

        self.processor_worker: Optional[ImageProcessorWorker] = None
        self.drawing_worker: Optional[DrawingEngineWorker] = None
        self.progress_dialog: Optional[DrawingProgressDialog] = None

        self._init_ui()
        self._load_saved_defaults()

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

        # --- 1. HEADER ---
        header_card = QFrame(self)
        header_card.setObjectName("Card")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)

        v_head = QVBoxLayout()
        lbl_title = QLabel("🎨 AutoDraw", self)
        lbl_title.setObjectName("HeaderTitle")
        lbl_subtitle = QLabel("Transforme qualquer imagem em traços automáticos.", self)
        lbl_subtitle.setObjectName("HeaderSubtitle")
        v_head.addWidget(lbl_title)
        v_head.addWidget(lbl_subtitle)
        header_layout.addLayout(v_head)

        header_layout.addStretch()

        btn_settings = QPushButton("⚙️", self)
        btn_settings.setFixedSize(38, 38)
        btn_settings.setToolTip("Configurações")
        btn_settings.clicked.connect(self._open_settings)
        header_layout.addWidget(btn_settings)

        scroll_layout.addWidget(header_card)

        # --- 2. IMAGE CARD & PREVIEW ---
        img_card = QFrame(self)
        img_card.setObjectName("Card")
        img_layout = QVBoxLayout(img_card)
        img_layout.setContentsMargins(16, 16, 16, 16)
        img_layout.setSpacing(10)

        # Controls Row
        top_img_row = QHBoxLayout()
        self.btn_choose_image = QPushButton("📁 ESCOLHER IMAGEM", self)
        self.btn_choose_image.setFixedHeight(38)
        self.btn_choose_image.clicked.connect(self._choose_image_dialog)
        top_img_row.addWidget(self.btn_choose_image)

        self.lbl_image_info = QLabel("Nenhuma imagem selecionada", self)
        self.lbl_image_info.setObjectName("Badge")
        top_img_row.addWidget(self.lbl_image_info)
        top_img_row.addStretch()

        img_layout.addLayout(top_img_row)

        # Tab/Toggle buttons for Canvas Preview Mode
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        
        self.btn_tab_proc = QPushButton("🎨 Resultado Processado", self)
        self.btn_tab_proc.setObjectName("TabButton")
        self.btn_tab_proc.setCheckable(True)
        self.btn_tab_proc.setChecked(True)
        self.btn_tab_proc.clicked.connect(lambda: self._set_preview_mode("processed"))
        tab_row.addWidget(self.btn_tab_proc)

        self.btn_tab_orig = QPushButton("🖼️ Imagem Original", self)
        self.btn_tab_orig.setObjectName("TabButton")
        self.btn_tab_orig.setCheckable(True)
        self.btn_tab_orig.clicked.connect(lambda: self._set_preview_mode("original"))
        tab_row.addWidget(self.btn_tab_orig)

        self.btn_tab_area = QPushButton("📐 Simulação no Paint", self)
        self.btn_tab_area.setObjectName("TabButton")
        self.btn_tab_area.setCheckable(True)
        self.btn_tab_area.clicked.connect(lambda: self._set_preview_mode("area"))
        tab_row.addWidget(self.btn_tab_area)

        tab_row.addStretch()
        img_layout.addLayout(tab_row)

        # Dual Preview Canvas
        self.preview_canvas = ImagePreviewCanvas(self)
        img_layout.addWidget(self.preview_canvas)

        # Recent Images Bar
        self.recent_bar = RecentImagesBar(self)
        self.recent_bar.image_selected.connect(self._load_image_from_path)
        img_layout.addWidget(self.recent_bar)

        scroll_layout.addWidget(img_card)

        # --- 3. QUALITY & ADJUSTMENTS CARD ---
        opts_card = QFrame(self)
        opts_card.setObjectName("Card")
        opts_layout = QVBoxLayout(opts_card)
        opts_layout.setContentsMargins(16, 16, 16, 16)
        opts_layout.setSpacing(12)

        lbl_opts_title = QLabel("⚙️ Configuração do Desenho", self)
        lbl_opts_title.setObjectName("SectionTitle")
        opts_layout.addWidget(lbl_opts_title)

        # Quality Dropdown Row
        q_row = QHBoxLayout()
        lbl_q = QLabel("Qualidade do desenho:", self)
        lbl_q.setStyleSheet("font-weight: 600;")
        q_row.addWidget(lbl_q)

        self.cmb_quality = QComboBox(self)
        self.cmb_quality.addItems(["Baixa", "Média", "Alta"])
        self.cmb_quality.setCurrentIndex(1)  # Default 'Média'
        self.cmb_quality.currentIndexChanged.connect(self._recalculate_preview_async)
        q_row.addWidget(self.cmb_quality)

        q_row.addStretch()
        opts_layout.addLayout(q_row)

        # Aspect Ratio Row
        aspect_row = QHBoxLayout()
        lbl_aspect = QLabel("Ajuste da Imagem:", self)
        lbl_aspect.setStyleSheet("font-weight: 600;")
        aspect_row.addWidget(lbl_aspect)

        self.btn_group_aspect = QButtonGroup(self)
        self.radio_aspect_keep = QRadioButton("Manter proporção", self)
        self.radio_aspect_fill = QRadioButton("Preencher área", self)
        self.radio_aspect_stretch = QRadioButton("Esticar", self)

        self.btn_group_aspect.addButton(self.radio_aspect_keep, 0)
        self.btn_group_aspect.addButton(self.radio_aspect_fill, 1)
        self.btn_group_aspect.addButton(self.radio_aspect_stretch, 2)

        aspect_row.addWidget(self.radio_aspect_keep)
        aspect_row.addWidget(self.radio_aspect_fill)
        aspect_row.addWidget(self.radio_aspect_stretch)
        aspect_row.addStretch()
        opts_layout.addLayout(aspect_row)

        self.btn_group_aspect.idClicked.connect(self._recalculate_preview_async)

        # Speed Slider Row
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
        self.slider_speed.valueChanged.connect(self._recalculate_preview_async)
        speed_row.addWidget(self.slider_speed)

        lbl_fast = QLabel("Rápido", self)
        lbl_fast.setStyleSheet("color: #64748B; font-size: 11px;")
        speed_row.addWidget(lbl_fast)

        opts_layout.addLayout(speed_row)

        # Simplify Checkbox
        self.chk_simplify = QCheckBox("Simplificar imagem (remover ruídos pequenos)", self)
        self.chk_simplify.toggled.connect(self._recalculate_preview_async)
        opts_layout.addWidget(self.chk_simplify)

        scroll_layout.addWidget(opts_card)

        # --- 4. AREA SELECTION CARD ---
        area_card = QFrame(self)
        area_card.setObjectName("Card")
        area_layout = QHBoxLayout(area_card)
        area_layout.setContentsMargins(16, 14, 16, 14)
        area_layout.setSpacing(12)

        self.btn_select_area = QPushButton("🖱️ SELECIONAR ÁREA DE DESENHO", self)
        self.btn_select_area.setFixedHeight(42)
        self.btn_select_area.clicked.connect(self._start_area_selection)
        area_layout.addWidget(self.btn_select_area)

        self.lbl_area_status = QLabel("Área: ❌ Não selecionada", self)
        self.lbl_area_status.setObjectName("BadgeWarning")
        area_layout.addWidget(self.lbl_area_status)

        scroll_layout.addWidget(area_card)

        # --- 5. ACTION & ESTIMATED TIME ---
        action_card = QFrame(self)
        action_card.setObjectName("Card")
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(16, 16, 16, 16)
        action_layout.setSpacing(10)

        self.lbl_estimated_time = QLabel("⏱ Tempo estimado: --", self)
        self.lbl_estimated_time.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_estimated_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_estimated_time.setStyleSheet("color: #4ADE80;")
        action_layout.addWidget(self.lbl_estimated_time)

        self.lbl_trajectory_summary = QLabel("Aguardando seleção de imagem e área...", self)
        self.lbl_trajectory_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_trajectory_summary.setStyleSheet("color: #94A3B8; font-size: 12px;")
        action_layout.addWidget(self.lbl_trajectory_summary)

        self.btn_draw = QPushButton("▶ DESENHAR", self)
        self.btn_draw.setObjectName("PrimaryButton")
        self.btn_draw.setFixedHeight(50)
        self.btn_draw.setEnabled(False)
        self.btn_draw.clicked.connect(self._start_drawing_process)
        action_layout.addWidget(self.btn_draw)

        scroll_layout.addWidget(action_card)

        # --- 6. SAFETY FOOTER ---
        footer_badge = QLabel("⚡ Pressione ESC a qualquer momento para cancelar o desenho", self)
        footer_badge.setObjectName("BadgeWarning")
        footer_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(footer_badge)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

    # --- DRAG & DROP HANDLERS ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fp = url.toLocalFile()
                if ImageLoader.is_supported(fp):
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
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fp = url.toLocalFile()
                if ImageLoader.is_supported(fp):
                    self._load_image_from_path(fp)
                    event.acceptProposedAction()
                    return
                else:
                    QMessageBox.warning(
                        self, "Formato não suportado",
                        "❌ Formato de imagem não suportado.\n\nAceitos: PNG, JPG, JPEG, BMP, WEBP, GIF, SVG, TIFF"
                    )

    def _set_preview_mode(self, mode: str):
        self.btn_tab_proc.setChecked(mode == "processed")
        self.btn_tab_orig.setChecked(mode == "original")
        self.btn_tab_area.setChecked(mode == "area")
        self.preview_canvas.set_view_mode(mode)

    def _load_saved_defaults(self):
        recent_files = self.config_manager.get("recent_images", [])
        self.recent_bar.set_recent_files(recent_files)

        if self.selected_area:
            w, h = self.selected_area.get("w", 0), self.selected_area.get("h", 0)
            x, y = self.selected_area.get("x", 0), self.selected_area.get("y", 0)
            if w > 0 and h > 0:
                self.lbl_area_status.setText(f"Área: {w}×{h} px em ({x}, {y})")
                self.lbl_area_status.setObjectName("BadgeSuccess")
                self.lbl_area_status.setStyle(self.lbl_area_status.style())

        q_lvl = self.config_manager.get("quality_level", "media").lower()
        if q_lvl == "baixa":
            self.cmb_quality.setCurrentIndex(0)
        elif q_lvl == "alta":
            self.cmb_quality.setCurrentIndex(2)
        else:
            self.cmb_quality.setCurrentIndex(1)

        aspect = self.config_manager.get("aspect_mode", "keep_aspect")
        if aspect == "fill":
            self.radio_aspect_fill.setChecked(True)
        elif aspect == "stretch":
            self.radio_aspect_stretch.setChecked(True)
        else:
            self.radio_aspect_keep.setChecked(True)

        self.slider_speed.setValue(self.config_manager.get("speed", 50))
        self.chk_simplify.setChecked(self.config_manager.get("simplify_image", False))

    def _choose_image_dialog(self):
        file_filter = "Imagens Suportadas (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.svg *.tif *.tiff);;Todos os arquivos (*.*)"
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Escolher imagem para AutoDraw", "", file_filter
        )
        if filepath:
            self._load_image_from_path(filepath)

    def _load_image_from_path(self, filepath: str):
        info = ImageLoader.load_image(filepath)
        if info:
            self.current_image_info = info
            self.config_manager.add_recent_image(filepath)
            self.recent_bar.set_recent_files(self.config_manager.get("recent_images", []))

            self.lbl_image_info.setText(f"{info.filename} — {info.width} × {info.height} px")
            self.lbl_image_info.setObjectName("BadgeSuccess")
            self.lbl_image_info.setStyle(self.lbl_image_info.style())

            self.preview_canvas.set_image(info.cv_image)
            self._recalculate_preview_async()
            self._update_draw_button_state()

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

        self.lbl_area_status.setText(f"Área: {w}×{h} px em ({x}, {y})")
        self.lbl_area_status.setObjectName("BadgeSuccess")
        self.lbl_area_status.setStyle(self.lbl_area_status.style())

        self.show()
        self.raise_()
        self.activateWindow()

        self._recalculate_preview_async()
        self._update_draw_button_state()

    @Slot()
    def _on_area_selection_cancelled(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _get_current_quality_str(self) -> str:
        idx = self.cmb_quality.currentIndex()
        if idx == 0:
            return "baixa"
        elif idx == 2:
            return "alta"
        return "media"

    def _recalculate_preview_async(self):
        if not self.current_image_info or not self.selected_area:
            return

        q_lvl = self._get_current_quality_str()
        self.config_manager.set("quality_level", q_lvl)

        target_w = self.selected_area["w"]
        target_h = self.selected_area["h"]

        if self.radio_aspect_fill.isChecked():
            aspect_mode = "fill"
        elif self.radio_aspect_stretch.isChecked():
            aspect_mode = "stretch"
        else:
            aspect_mode = "keep_aspect"

        simplify = self.chk_simplify.isChecked()
        speed = self.slider_speed.value()
        calib = self.config_manager.get("calibration_factor", 1.0)

        self.lbl_estimated_time.setText("⏱ Analisando imagem...")

        # Terminate any running processor worker
        if self.processor_worker and self.processor_worker.isRunning():
            self.processor_worker.terminate()

        self.processor_worker = ImageProcessorWorker(
            cv_img=self.current_image_info.cv_image,
            target_w=target_w,
            target_h=target_h,
            mode="contour",
            aspect_mode=aspect_mode,
            quality_level=q_lvl,
            simplify_image=simplify,
            speed=speed,
            calibration_factor=calib,
            parent=self
        )

        self.processor_worker.processing_finished.connect(self._on_processing_finished)
        self.processor_worker.start()

    @Slot(list, float, int)
    def _on_processing_finished(self, strokes: list, est_seconds: float, total_pts: int):
        self.processed_strokes = strokes
        self.estimated_seconds = est_seconds

        target_w = self.selected_area["w"] if self.selected_area else 0
        target_h = self.selected_area["h"] if self.selected_area else 0

        self.preview_canvas.set_vector_paths(strokes, target_w, target_h)

        t_str = TimeEstimator.format_time(est_seconds)
        self.lbl_estimated_time.setText(f"⏱ Tempo estimado: ≈ {t_str}")

        self.lbl_trajectory_summary.setText(
            f"Traços: {len(strokes):,} | Pontos: {total_pts:,} | Qualidade: {self._get_current_quality_str().capitalize()}"
        )

    def _update_draw_button_state(self):
        has_image = self.current_image_info is not None
        has_area = self.selected_area is not None and self.selected_area.get("w", 0) > 0
        self.btn_draw.setEnabled(has_image and has_area)

    def _open_settings(self):
        dlg = SettingsDialog(self.config_manager, self)
        if dlg.exec():
            self._load_saved_defaults()
            self._recalculate_preview_async()

    def _start_drawing_process(self):
        if not self.current_image_info or not self.selected_area or not self.processed_strokes:
            QMessageBox.warning(self, "Aviso", "Por favor, selecione uma imagem e área de desenho.")
            return

        skip_confirm = self.config_manager.get("skip_confirmation", False)

        if not skip_confirm:
            dlg = ConfirmationDialog(
                filename=self.current_image_info.filename,
                img_w=self.current_image_info.width,
                img_h=self.current_image_info.height,
                quality_level=self._get_current_quality_str(),
                area_w=self.selected_area["w"],
                area_h=self.selected_area["h"],
                total_strokes=len(self.processed_strokes),
                estimated_sec=self.estimated_seconds,
                parent=self
            )
            if not dlg.exec():
                return
            if dlg.skip_future:
                self.config_manager.set("skip_confirmation", True)

        # 3-Second Countdown
        countdown = CountdownOverlayDialog(countdown_sec=3, parent=self)
        if not countdown.exec():
            return

        self._execute_drawing()

    def _execute_drawing(self):
        start_x = self.selected_area["x"]
        start_y = self.selected_area["y"]
        speed = self.slider_speed.value()

        self.drawing_worker = DrawingEngineWorker(
            strokes=self.processed_strokes,
            start_x=start_x,
            start_y=start_y,
            speed=speed,
            estimated_total_seconds=self.estimated_seconds,
            parent=self
        )

        show_progress = self.config_manager.get("show_progress", True)
        sound_on_finish = self.config_manager.get("sound_on_finish", True)

        self.progress_dialog = DrawingProgressDialog(
            total_strokes=len(self.processed_strokes),
            estimated_total_sec=self.estimated_seconds,
            sound_on_finish=sound_on_finish,
            parent=self
        )

        self.drawing_worker.progress_changed.connect(self.progress_dialog.update_progress)
        self.drawing_worker.drawing_finished.connect(self._on_drawing_finished)
        self.drawing_worker.drawing_cancelled.connect(self._on_drawing_cancelled)
        self.drawing_worker.drawing_error.connect(self._on_drawing_error)

        self.progress_dialog.pause_requested.connect(self.drawing_worker.pause)
        self.progress_dialog.resume_requested.connect(self.drawing_worker.resume)
        self.progress_dialog.stop_requested.connect(self.drawing_worker.stop)

        self.drawing_worker.start()

        if show_progress:
            self.progress_dialog.exec()

    @Slot(float, int, int)
    def _on_drawing_finished(self, actual_elapsed: float, total_strokes: int, total_pts: int):
        if self.progress_dialog:
            self.progress_dialog.on_finished()

        # Auto-calibrate time estimator factor based on actual execution performance
        if self.estimated_seconds > 0 and actual_elapsed > 0:
            current_factor = self.config_manager.get("calibration_factor", 1.0)
            ratio = actual_elapsed / self.estimated_seconds
            new_factor = max(0.4, min(3.0, current_factor * 0.7 + ratio * 0.3))
            self.config_manager.set("calibration_factor", new_factor)

        # Show Completion Dialog
        dlg = CompletionDialog(
            elapsed_seconds=actual_elapsed,
            quality_level=self._get_current_quality_str(),
            total_strokes=total_strokes,
            parent=self
        )
        dlg.repeat_requested.connect(self._execute_drawing)
        dlg.exec()

    @Slot(str)
    def _on_drawing_cancelled(self, reason: str):
        if self.progress_dialog:
            self.progress_dialog.reject()
        QMessageBox.warning(
            self, "Cancelado", f"O desenho foi cancelado: {reason}"
        )

    @Slot(str)
    def _on_drawing_error(self, err_msg: str):
        if self.progress_dialog:
            self.progress_dialog.reject()
        QMessageBox.critical(
            self, "Erro", f"Ocorreu um erro durante o desenho:\n{err_msg}"
        )
