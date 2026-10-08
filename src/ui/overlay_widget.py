from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QGuiApplication
from PySide6.QtWidgets import QWidget


class AreaSelectionOverlay(QWidget):
    """
    Full-screen semi-transparent overlay allowing the user to click and drag
    a bounding box on screen to define the drawing canvas area.
    """
    area_selected = Signal(int, int, int, int)  # x, y, width, height
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos: QPoint = QPoint()
        self._current_pos: QPoint = QPoint()
        self._is_selecting: bool = False

        # Calculate bounding geometry of all connected monitors
        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())

        self.setGeometry(total_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._current_pos = self._start_pos
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._current_pos = event.globalPosition().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._is_selecting = False
            self._current_pos = event.globalPosition().toPoint()
            
            rect = QRect(self._start_pos, self._current_pos).normalized()
            
            # Require minimum rectangle size (e.g. at least 20x20 px)
            if rect.width() >= 20 and rect.height() >= 20:
                self.area_selected.emit(
                    rect.x(), rect.y(), rect.width(), rect.height()
                )
            else:
                self.cancelled.emit()
            
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Dark dim background overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._is_selecting:
            rect = QRect(self._start_pos, self._current_pos).normalized()

            # 2. Clear selected area (punch hole in background)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 0))

            # 3. Draw border and guides over selected area
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Cyan/Indigo dashed outline
            pen = QPen(QColor("#6366F1"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Solid outer line
            painter.setPen(QPen(QColor("#818CF8"), 1, Qt.PenStyle.SolidLine))
            painter.drawRect(rect)

            # Dimensions badge text
            badge_text = f" Área de Desenho: {rect.width()} × {rect.height()} px "
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            
            # Draw badge background above selection
            badge_w = 260
            badge_h = 32
            badge_x = max(rect.x(), min(rect.x() + (rect.width() - badge_w) // 2, self.width() - badge_w - 10))
            badge_y = rect.y() - badge_h - 8 if rect.y() >= badge_h + 10 else rect.y() + 8

            badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#1E2034")))
            painter.drawRoundedRect(badge_rect, 6, 6)

            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
        else:
            # Draw helpful instruction text in center of screen
            instruction = "Clique e arraste com o mouse para selecionar a área do desenho\n\n[ Pressione ESC para cancelar ]"
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, instruction)
