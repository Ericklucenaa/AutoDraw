import os
from typing import List, Tuple, Optional
import numpy as np
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QImage, QPixmap, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel


class ImagePreviewCanvas(QWidget):
    """
    Dual-view canvas that renders:
    1) Original image
    2) Vectorized drawing stroke result
    3) Area fit simulation inside Paint canvas bounds
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setMinimumWidth(320)
        self.setStyleSheet(
            "background-color: #12131C; border: 1px dashed #3F4468; border-radius: 10px;"
        )

        self._cv_image: Optional[np.ndarray] = None
        self._pixmap: Optional[QPixmap] = None
        self._strokes: List[List[Tuple[int, int]]] = []
        self._target_w: int = 0
        self._target_h: int = 0

        self.view_mode: str = "processed"  # 'processed', 'original', 'area'
        self.is_drag_hover: bool = False

    def set_drag_hover(self, hovering: bool) -> None:
        self.is_drag_hover = hovering
        if hovering:
            self.setStyleSheet("background-color: #1E1B4B; border: 2px dashed #818CF8; border-radius: 10px;")
        else:
            self.setStyleSheet("background-color: #12131C; border: 1px dashed #3F4468; border-radius: 10px;")
        self.update()

    def set_image(self, cv_image: Optional[np.ndarray]) -> None:
        self._cv_image = cv_image
        if cv_image is not None:
            h, w, ch = cv_image.shape
            bytes_per_line = ch * w
            rgb = cv_image.copy()[:, :, ::-1]  # BGR to RGB
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(qimg)
        else:
            self._pixmap = None
            self._strokes = []
        self.update()

    def set_vector_paths(
        self, strokes: List[List[Tuple[int, int]]], target_w: int, target_h: int
    ) -> None:
        self._strokes = strokes
        self._target_w = target_w
        self._target_h = target_h
        self.update()

    def set_view_mode(self, mode: str) -> None:
        self.view_mode = mode
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # Drag hover overlay
        if self.is_drag_hover:
            painter.fillRect(rect, QColor(99, 102, 241, 60))
            painter.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#A5B4FC")))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "📥 SOLTE A IMAGEM AQUI\n\n(PNG, JPG, BMP, WEBP, GIF, SVG)",
            )
            return

        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QPen(QColor("#64748B"), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 8, 8)

            painter.setFont(QFont("Segoe UI", 13))
            painter.setPen(QPen(QColor("#94A3B8")))
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "🖼️ ARRASTE SUA IMAGEM AQUI\n\nou clique em 'Escolher imagem'",
            )
            return

        scaled_pixmap = self._pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        img_x = (rect.width() - scaled_pixmap.width()) // 2
        img_y = (rect.height() - scaled_pixmap.height()) // 2
        img_rect = QRect(img_x, img_y, scaled_pixmap.width(), scaled_pixmap.height())

        if self.view_mode == "original":
            painter.drawPixmap(img_rect, scaled_pixmap)

        elif self.view_mode == "processed":
            # Dark background canvas for crisp vector line visibility
            painter.fillRect(img_rect, QColor(15, 16, 23, 230))
            painter.drawPixmap(img_rect, scaled_pixmap)
            painter.fillRect(img_rect, QColor(15, 16, 23, 140))

            if self._strokes and self._target_w > 0 and self._target_h > 0:
                scale_x = scaled_pixmap.width() / float(self._target_w)
                scale_y = scaled_pixmap.height() / float(self._target_h)

                pen = QPen(QColor("#38BDF8"), 1.4, Qt.PenStyle.SolidLine)
                painter.setPen(pen)

                for stroke in self._strokes:
                    if len(stroke) < 2:
                        continue
                    path = QPainterPath()
                    first_pt = stroke[0]
                    sx = img_x + first_pt[0] * scale_x
                    sy = img_y + first_pt[1] * scale_y
                    path.moveTo(sx, sy)

                    for pt in stroke[1:]:
                        px = img_x + pt[0] * scale_x
                        py = img_y + pt[1] * scale_y
                        path.lineTo(px, py)

                    painter.drawPath(path)

        elif self.view_mode == "area":
            # Canvas simulation
            painter.fillRect(img_rect, QColor(30, 32, 52))
            pen_box = QPen(QColor("#6366F1"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen_box)
            painter.drawRect(img_rect)

            if self._strokes and self._target_w > 0 and self._target_h > 0:
                scale_x = scaled_pixmap.width() / float(self._target_w)
                scale_y = scaled_pixmap.height() / float(self._target_h)

                pen_line = QPen(QColor("#4ADE80"), 1.2, Qt.PenStyle.SolidLine)
                painter.setPen(pen_line)

                for stroke in self._strokes:
                    if len(stroke) < 2:
                        continue
                    path = QPainterPath()
                    first_pt = stroke[0]
                    sx = img_x + first_pt[0] * scale_x
                    sy = img_y + first_pt[1] * scale_y
                    path.moveTo(sx, sy)

                    for pt in stroke[1:]:
                        px = img_x + pt[0] * scale_x
                        py = img_y + pt[1] * scale_y
                        path.lineTo(px, py)

                    painter.drawPath(path)

            badge_text = f" Simulação no Paint: {self._target_w}×{self._target_h} px "
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(img_rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, badge_text)

        # Border
        painter.setPen(QPen(QColor("#3F4468"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 10, 10)


class RecentImagesBar(QWidget):
    """Horizontal bar displaying pill buttons for recently opened images."""

    image_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 4, 0, 4)
        self.layout.setSpacing(6)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def set_recent_files(self, filepaths: List[str]) -> None:
        while self.layout.count() > 0:
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not filepaths:
            return

        lbl = QLabel("Recentes:", self)
        lbl.setStyleSheet("color: #64748B; font-size: 11px;")
        self.layout.addWidget(lbl)

        for fp in filepaths:
            if not os.path.exists(fp):
                continue
            filename = os.path.basename(fp)
            if len(filename) > 18:
                filename = filename[:15] + "..."

            btn = QPushButton(f"📄 {filename}", self)
            btn.setObjectName("PillButton")
            btn.setToolTip(fp)
            btn.clicked.connect(lambda _, path=fp: self.image_selected.emit(path))
            self.layout.addWidget(btn)
