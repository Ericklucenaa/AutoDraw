import os
from dataclasses import dataclass


import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from src.logger import get_logger

log = get_logger("loader")

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".svg", ".tif", ".tiff"}
SUPPORTED_LABEL = "PNG, JPG, JPEG, BMP, WEBP, GIF, SVG, TIFF"

# SVG has no intrinsic pixel size; render so the shorter side reaches this many
# pixels, which gives the edge detector enough detail to work with.
SVG_MIN_SIDE = 512
SVG_MAX_SIDE = 4096


class ImageLoadError(Exception):
    """Raised with a user-facing message when an image cannot be loaded."""


@dataclass
class ImageInfo:
    filepath: str
    filename: str
    width: int
    height: int
    aspect_ratio: float
    cv_image: np.ndarray  # BGR format (3-channel)


class ImageLoader:
    """Handles loading, validating, rendering SVG/GIF/PNG transparent images, and retrieving metadata."""

    @staticmethod
    def is_supported(filepath: str) -> bool:
        if not filepath:
            return False
        return os.path.splitext(filepath)[1].lower() in SUPPORTED_EXTENSIONS

    @staticmethod
    def load_image(filepath: str) -> ImageInfo:
        """
        Loads any supported image as a 3-channel BGR array.

        Raises ImageLoadError with a message meant for the user; callers show
        it instead of silently doing nothing.
        """
        if not filepath:
            raise ImageLoadError("Nenhum arquivo informado.")
        if not os.path.exists(filepath):
            raise ImageLoadError(f"Arquivo não encontrado:\n{filepath}")

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ImageLoadError(
                f"Formato {ext or 'desconhecido'} não suportado.\n\nAceitos: {SUPPORTED_LABEL}"
            )

        cv_img = ImageLoader._render_svg(filepath) if ext == ".svg" else ImageLoader._load_raster(filepath)

        if cv_img is None or cv_img.size == 0:
            raise ImageLoadError(f"A imagem está vazia ou corrompida:\n{os.path.basename(filepath)}")

        height, width = cv_img.shape[:2]
        log.info("Loaded %s (%dx%d)", os.path.basename(filepath), width, height)

        return ImageInfo(
            filepath=filepath,
            filename=os.path.basename(filepath),
            width=width,
            height=height,
            aspect_ratio=width / float(height) if height > 0 else 1.0,
            cv_image=cv_img,
        )

    @staticmethod
    def try_load_image(filepath: str):
        """Convenience wrapper returning (info, error_message)."""
        try:
            return ImageLoader.load_image(filepath), None
        except ImageLoadError as e:
            log.warning("Load failed for %s: %s", filepath, e)
            return None, str(e)

    # ---------------- format handlers ----------------

    @staticmethod
    def _render_svg(filepath: str) -> np.ndarray:
        renderer = QSvgRenderer(filepath)
        if not renderer.isValid():
            raise ImageLoadError(f"SVG inválido ou não suportado:\n{os.path.basename(filepath)}")

        default_size = renderer.defaultSize()
        natural_w = default_size.width()
        natural_h = default_size.height()
        if natural_w <= 0 or natural_h <= 0:
            natural_w = natural_h = SVG_MIN_SIDE

        # Scale uniformly: scaling each side independently to a floor would
        # stretch a wide drawing into a square.
        scale = max(1.0, SVG_MIN_SIDE / float(min(natural_w, natural_h)))
        scale = min(scale, SVG_MAX_SIDE / float(max(natural_w, natural_h)))
        width = max(1, int(round(natural_w * scale)))
        height = max(1, int(round(natural_h * scale)))

        qimg = QImage(width, height, QImage.Format.Format_ARGB32)
        qimg.fill(QColor(255, 255, 255, 255))  # White background

        painter = QPainter(qimg)
        try:
            renderer.render(painter, QRectF(0, 0, width, height))
        finally:
            painter.end()

        return qimage_to_bgr(qimg)

    @staticmethod
    def _load_raster(filepath: str) -> np.ndarray:
        try:
            with Image.open(filepath) as pil_img:
                # Multi-frame formats (GIF, animated WEBP): use the first frame.
                if getattr(pil_img, "is_animated", False):
                    pil_img.seek(0)

                has_alpha = pil_img.mode in ("RGBA", "LA") or (
                    pil_img.mode == "P" and "transparency" in pil_img.info
                )
                if has_alpha:
                    rgba = pil_img.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    rgb_img = Image.alpha_composite(background, rgba).convert("RGB")
                else:
                    rgb_img = pil_img.convert("RGB")

                return cv2.cvtColor(np.asarray(rgb_img), cv2.COLOR_RGB2BGR)
        except (UnidentifiedImageError, ValueError) as e:
            raise ImageLoadError(
                f"Não foi possível decodificar a imagem:\n{os.path.basename(filepath)}\n\n({e})"
            ) from e
        except OSError as e:
            raise ImageLoadError(
                f"Erro ao ler o arquivo:\n{os.path.basename(filepath)}\n\n({e})"
            ) from e


def qimage_to_bgr(qimg: QImage) -> np.ndarray:
    """
    Converts a QImage to a contiguous BGR array, honouring the scanline stride.

    QImage pads every scanline to a 4-byte boundary, so for Format_RGB888 the
    buffer is bytesPerLine * height, not width * 3 * height. Reshaping to
    (h, w, 3) only happens to work when width * 3 is already a multiple of 4,
    which is why SVGs of most widths used to fail outright.
    """
    rgb = qimg.convertToFormat(QImage.Format.Format_RGB888)
    width, height = rgb.width(), rgb.height()
    stride = rgb.bytesPerLine()

    buffer = np.frombuffer(memoryview(rgb.constBits()), dtype=np.uint8, count=stride * height)
    rows = buffer.reshape(height, stride)[:, : width * 3]
    arr = np.ascontiguousarray(rows.reshape(height, width, 3))

    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
