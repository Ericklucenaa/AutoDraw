import os
from dataclasses import dataclass
from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtSvg import QSvgRenderer

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".svg", ".tif", ".tiff"}


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
        ext = os.path.splitext(filepath)[1].lower()
        return ext in SUPPORTED_EXTENSIONS

    @staticmethod
    def load_image(filepath: str) -> Optional[ImageInfo]:
        if not filepath or not os.path.exists(filepath):
            return None

        ext = os.path.splitext(filepath)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            print(f"[ImageLoader] Unsupported file extension: {ext}")
            return None

        try:
            # 1. Handle SVG files using PySide6 QSvgRenderer
            if ext == ".svg":
                renderer = QSvgRenderer(filepath)
                if not renderer.isValid():
                    return None
                
                size = renderer.defaultSize()
                w = max(400, size.width())
                h = max(400, size.height())

                qimg = QImage(w, h, QImage.Format.Format_ARGB32)
                qimg.fill(QColor(255, 255, 255, 255))  # White background

                painter = QPainter(qimg)
                renderer.render(painter, QRectF(0, 0, w, h))
                painter.end()

                # Convert QImage to BGR numpy array
                qimg = qimg.convertToFormat(QImage.Format.Format_RGB888)
                ptr = qimg.bits()
                arr = np.array(ptr, dtype=np.uint8).reshape((h, w, 3))
                cv_img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

            else:
                # 2. Handle raster formats (PNG, JPG, WEBP, GIF, TIFF) via PIL
                pil_img = Image.open(filepath)

                # For multi-frame images like GIF, seek to first frame
                if getattr(pil_img, "is_animated", False):
                    pil_img.seek(0)

                # Handle transparency (RGBA / LA / P with alpha)
                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    rgba_img = pil_img.convert("RGBA")
                    # Create solid white background
                    background = Image.new("RGBA", rgba_img.size, (255, 255, 255, 255))
                    # Composite transparent image onto white background
                    composite = Image.alpha_composite(background, rgba_img)
                    rgb_img = composite.convert("RGB")
                else:
                    rgb_img = pil_img.convert("RGB")

                cv_img = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)

            h, w = cv_img.shape[:2]
            aspect_ratio = w / float(h) if h > 0 else 1.0

            return ImageInfo(
                filepath=filepath,
                filename=os.path.basename(filepath),
                width=w,
                height=h,
                aspect_ratio=aspect_ratio,
                cv_image=cv_img
            )

        except Exception as e:
            print(f"[ImageLoader] Error loading image '{filepath}': {e}")
            return None
