import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Let Qt run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Redirect the app directory before anything under src/ is imported. Modules
# call get_logger() at import time, which opens the log file immediately, so a
# per-test fixture would be too late and the suite would write into the real
# ~/.autodraw/autodraw.log.
os.environ["AUTODRAW_HOME"] = tempfile.mkdtemp(prefix="autodraw-tests-")


@pytest.fixture(autouse=True)
def isolated_app_home(tmp_path_factory, monkeypatch):
    """Points AUTODRAW_HOME at a temp dir so tests never touch the user's config."""
    home = tmp_path_factory.mktemp("autodraw-home")
    monkeypatch.setenv("AUTODRAW_HOME", str(home))
    return home


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication for the whole session; Qt allows only one."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def sample_bgr():
    """A small synthetic drawing with clear edges."""
    import cv2
    import numpy as np

    canvas = np.full((200, 260, 3), 255, np.uint8)
    cv2.circle(canvas, (130, 100), 70, (0, 0, 0), 3)
    cv2.rectangle(canvas, (30, 30), (230, 170), (0, 0, 0), 2)
    cv2.line(canvas, (30, 170), (230, 30), (0, 0, 0), 2)
    return canvas
