import os
import sys

# Add project root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import __version__
from src.logger import get_logger, setup_logging
from src.mouse_controller import enable_dpi_awareness

log = get_logger("main")


def main():
    # Must run before Qt creates anything: with the process marked per-monitor
    # DPI aware, Win32 coordinates are real screen pixels, which is what the
    # drawing engine feeds to SetCursorPos.
    enable_dpi_awareness()

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AutoDraw")
    app.setOrganizationName("AutoDraw")
    app.setApplicationVersion(__version__)

    log_path = setup_logging()
    log.info("Starting AutoDraw %s (log: %s)", __version__, log_path)

    from src.ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    log.info("AutoDraw exited with code %s", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
