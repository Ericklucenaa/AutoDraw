import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from src.image_loader import SUPPORTED_LABEL

Stroke = List[Tuple[int, int]]

_IDLE_STYLE = "background-color: #12131C; border: 1px dashed #3F4468; border-radius: 10px;"
_HOVER_STYLE = "background-color: #1E1B4B; border: 2px dashed #818CF8; border-radius: 10px;"


def cv_to_pixmap(cv_image: np.ndarray) -> Optional[QPixmap]:
    """
    Converts a BGR (or grayscale) OpenCV array to a QPixmap.

    cv2.cvtColor returns a C-contiguous buffer. Slicing with [:, :, ::-1]
    instead produces a reversed-stride view whose memoryview cannot be
    exported, which made QImage raise BufferError on every image load.
    """
    if cv_image is None or cv_image.size == 0:
        return None

    if cv_image.ndim == 2:
        rgb = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

    height, width = rgb.shape[:2]
    qimg = QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888)
    # QImage wraps the numpy buffer without owning it; copy() detaches the
    # pixels so the pixmap stays valid after `rgb` is garbage collected.
    return QPixmap.fromImage(qimg.copy())


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
        self.setStyleSheet(_IDLE_STYLE)

        self._pixmap: Optional[QPixmap] = None
        self._strokes: List[Stroke] = []
        self._target_w: int = 0
        self._target_h: int = 0

        self.view_mode: str = "processed"  # 'processed', 'original', 'area'
        self.is_drag_hover: bool = False

    def set_drag_hover(self, hovering: bool) -> None:
        if hovering == self.is_drag_hover:
            return
        self.is_drag_hover = hovering
        self.setStyleSheet(_HOVER_STYLE if hovering else _IDLE_STYLE)
        self.update()

    def set_image(self, cv_image: Optional[np.ndarray]) -> None:
        self._pixmap = cv_to_pixmap(cv_image) if cv_image is not None else None
        if self._pixmap is None:
            self._strokes = []
        self.update()

    def set_vector_paths(self, strokes: List[Stroke], target_w: int, target_h: int) -> None:
        self._strokes = strokes
        self._target_w = target_w
        self._target_h = target_h
        self.update()

    def clear_vector_paths(self) -> None:
        self._strokes = []
        self.update()

    def set_view_mode(self, mode: str) -> None:
        self.view_mode = mode
        self.update()

    # ---------------- painting ----------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        if self.is_drag_hover:
            self._paint_centered_message(
                painter, rect, "📥 SOLTE A IMAGEM AQUI", f"({SUPPORTED_LABEL})",
                QColor("#A5B4FC"), backdrop=QColor(99, 102, 241, 60),
            )
            return

        if self._pixmap is None or self._pixmap.isNull():
            painter.setPen(QPen(QColor("#64748B"), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 8, 8)
            self._paint_centered_message(
                painter, rect, "🖼️ ARRASTE SUA IMAGEM AQUI",
                "ou clique em 'Escolher imagem'", QColor("#94A3B8"),
            )
            return

        scaled = self._pixmap.scaled(
            rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        img_x = (rect.width() - scaled.width()) // 2
        img_y = (rect.height() - scaled.height()) // 2
        img_rect = QRect(img_x, img_y, scaled.width(), scaled.height())

        if self.view_mode == "original":
            painter.drawPixmap(img_rect, scaled)

        elif self.view_mode == "area":
            painter.fillRect(img_rect, QColor(30, 32, 52))
            painter.setPen(QPen(QColor("#6366F1"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(img_rect)
            self._paint_strokes(painter, img_rect, QColor("#4ADE80"), 1.2)

            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(
                img_rect,
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                f" Simulação no Paint: {self._target_w}×{self._target_h} px ",
            )

        else:  # 'processed'
            # Dark backdrop so the vector lines stay legible over the photo.
            painter.fillRect(img_rect, QColor(15, 16, 23, 230))
            painter.drawPixmap(img_rect, scaled)
            painter.fillRect(img_rect, QColor(15, 16, 23, 140))
            self._paint_strokes(painter, img_rect, QColor("#38BDF8"), 1.4)

        painter.setPen(QPen(QColor("#3F4468"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 10, 10)

    def _paint_strokes(self, painter: QPainter, img_rect: QRect, color: QColor, width: float) -> None:
        """Draws every stroke scaled from target-area space into img_rect."""
        if not self._strokes or self._target_w <= 0 or self._target_h <= 0:
            return

        scale_x = img_rect.width() / float(self._target_w)
        scale_y = img_rect.height() / float(self._target_h)
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine))

        # One QPainterPath for everything: a path per stroke meant tens of
        # thousands of draw calls per repaint on high quality settings.
        path = QPainterPath()
        for stroke in self._strokes:
            if len(stroke) < 2:
                continue
            path.moveTo(img_rect.x() + stroke[0][0] * scale_x, img_rect.y() + stroke[0][1] * scale_y)
            for px, py in stroke[1:]:
                path.lineTo(img_rect.x() + px * scale_x, img_rect.y() + py * scale_y)
        painter.drawPath(path)

    @staticmethod
    def _paint_centered_message(
        painter: QPainter,
        rect: QRect,
        title: str,
        subtitle: str,
        color: QColor,
        backdrop: Optional[QColor] = None,
    ) -> None:
        if backdrop is not None:
            painter.fillRect(rect, backdrop)
        painter.setPen(QPen(color))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{title}\n\n{subtitle}")


class RecentImagesBar(QWidget):
    """Horizontal bar displaying pill buttons for recently opened images."""

    image_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 4, 0, 4)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def set_recent_files(self, filepaths: List[str]) -> None:
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        existing = [fp for fp in filepaths if os.path.exists(fp)]
        if not existing:
            return

        label = QLabel("Recentes:", self)
        label.setStyleSheet("color: #64748B; font-size: 11px;")
        self._layout.addWidget(label)

        for filepath in existing:
            filename = os.path.basename(filepath)
            if len(filename) > 18:
                filename = filename[:15] + "..."

            button = QPushButton(f"📄 {filename}", self)
            button.setObjectName("PillButton")
            button.setToolTip(filepath)
            button.clicked.connect(lambda _=False, path=filepath: self.image_selected.emit(path))
            self._layout.addWidget(button)
