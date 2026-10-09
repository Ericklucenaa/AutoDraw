from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src.mouse_controller import MouseController

MIN_AREA_SIDE = 20


class AreaSelectionOverlay(QWidget):
    """
    Full-screen semi-transparent overlay allowing the user to click and drag
    a bounding box on screen to define the drawing canvas area.

    The emitted rectangle is in *physical* screen pixels, read straight from
    GetCursorPos. Qt reports mouse positions in its own logical coordinate
    space, so on a display scaled to 125% or 150% those values are smaller
    than the pixels SetCursorPos later addresses, and the drawing landed in
    the wrong place at the wrong size.
    """
    area_selected = Signal(int, int, int, int)  # x, y, width, height (physical px)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Logical coordinates drive the painting; physical ones are emitted.
        self._start_logical = QPoint()
        self._current_logical = QPoint()
        self._start_physical = (0, 0)
        self._current_physical = (0, 0)
        self._is_selecting = False
        self._resolved = False

        total_rect = QRect()
        for screen in QGuiApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)

    def showEvent(self, event):
        super().showEvent(event)
        # Without an explicit activate + focus the Tool window never receives
        # key events, so ESC could not cancel the selection.
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---------------- mouse ----------------

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._start_logical = event.globalPosition().toPoint()
        self._current_logical = self._start_logical
        self._start_physical = MouseController.get_cursor_pos()
        self._current_physical = self._start_physical
        self._is_selecting = True
        self.update()

    def mouseMoveEvent(self, event):
        if not self._is_selecting:
            return
        self._current_logical = event.globalPosition().toPoint()
        self._current_physical = MouseController.get_cursor_pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self._is_selecting:
            return

        self._is_selecting = False
        self._current_logical = event.globalPosition().toPoint()
        self._current_physical = MouseController.get_cursor_pos()

        physical = QRect(
            QPoint(*self._start_physical), QPoint(*self._current_physical)
        ).normalized()

        self._resolved = True
        if physical.width() >= MIN_AREA_SIDE and physical.height() >= MIN_AREA_SIDE:
            self.area_selected.emit(physical.x(), physical.y(), physical.width(), physical.height())
        else:
            self.cancelled.emit()
        self.close()

    # ---------------- keyboard & teardown ----------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._resolved = True
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        # Covers Alt+F4 and any other close path: without this the caller,
        # which hides its main window during selection, would never be told
        # to show it again.
        if not self._resolved:
            self._resolved = True
            self.cancelled.emit()
        super().closeEvent(event)

    # ---------------- painting ----------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if not self._is_selecting:
            painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#FFFFFF")))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Clique e arraste com o mouse para selecionar a área do desenho"
                "\n\n[ Pressione ESC para cancelar ]",
            )
            return

        rect = QRect(self._start_logical, self._current_logical).normalized()

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        painter.setPen(QPen(QColor("#6366F1"), 2, Qt.PenStyle.DashLine))
        painter.drawRect(rect)
        painter.setPen(QPen(QColor("#818CF8"), 1, Qt.PenStyle.SolidLine))
        painter.drawRect(rect)

        # Report the physical size, since that is what will actually be drawn.
        physical = QRect(QPoint(*self._start_physical), QPoint(*self._current_physical)).normalized()
        badge_text = f" Área de Desenho: {physical.width()} × {physical.height()} px "

        badge_w, badge_h = 260, 32
        badge_x = max(rect.x(), min(rect.x() + (rect.width() - badge_w) // 2, self.width() - badge_w - 10))
        badge_y = rect.y() - badge_h - 8 if rect.y() >= badge_h + 10 else rect.y() + 8
        badge_rect = QRect(badge_x, badge_y, badge_w, badge_h)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#1E2034")))
        painter.drawRoundedRect(badge_rect, 6, 6)

        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)
