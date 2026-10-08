import os
import sys
import numpy as np
import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import ConfigManager
from src.image_loader import ImageLoader
from src.contour_detector import ContourDetector
from src.path_optimizer import PathOptimizer
from src.image_processor import ImageProcessor
from src.time_estimator import TimeEstimator


def test_config_manager(tmp_path):
    config = ConfigManager()
    config.config_path = tmp_path / "config.json"
    config.set("quality_level", "alta")
    assert config.get("quality_level") == "alta"


def test_image_loader_transparency(tmp_path):
    img_path = str(tmp_path / "test_transparent.png")
    # Create RGBA image with transparent background and black rectangle
    rgba = np.zeros((100, 100, 4), dtype=np.uint8)
    rgba[20:80, 20:80] = [0, 0, 0, 255]  # opaque black rect

    # Write as PNG using cv2
    cv2.imwrite(img_path, rgba)

    info = ImageLoader.load_image(img_path)
    assert info is not None
    assert info.width == 100
    assert info.height == 100


def test_quality_levels():
    canvas = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.circle(canvas, (100, 100), 60, (255, 255, 255), 2)
    cv2.rectangle(canvas, (40, 40), (160, 160), (255, 255, 255), 2)

    strokes_baixa = ImageProcessor.process(canvas, 300, 300, quality_level="baixa")
    strokes_alta = ImageProcessor.process(canvas, 300, 300, quality_level="alta")

    pts_baixa = sum(len(s) for s in strokes_baixa)
    pts_alta = sum(len(s) for s in strokes_alta)

    # High quality must generate equal or more detailed points than low quality
    assert pts_alta >= pts_baixa


def test_time_estimator():
    strokes = [[(10, 10), (12, 12), (14, 14), (16, 16)], [(50, 50), (52, 52)]]
    sec = TimeEstimator.estimate_seconds(strokes, speed=50)
    assert sec > 0
    formatted = TimeEstimator.format_time(155.0)
    assert formatted == "2m 35s"


def test_path_optimizer():
    strokes = [
        [(100, 100), (110, 110)],
        [(10, 10), (20, 20)],
        [(150, 150), (160, 160)]
    ]
    optimized = PathOptimizer.optimize_paths(strokes)
    assert len(optimized) == 3
    assert optimized[0][0] == (10, 10)
