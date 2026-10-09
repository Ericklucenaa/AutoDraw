import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_configured = False


def app_dir() -> Path:
    """Returns the per-user AutoDraw directory, honouring AUTODRAW_HOME for tests."""
    override = os.environ.get("AUTODRAW_HOME")
    base = Path(override) if override else Path.home() / ".autodraw"
    base.mkdir(parents=True, exist_ok=True)
    return base


def setup_logging(level: int = logging.INFO, log_dir: Optional[Path] = None) -> Path:
    """
    Configures file + stderr logging once per process.

    A file handler matters for the frozen build: PyInstaller's --windowed mode
    discards stdout, so print() based diagnostics are invisible in the .exe.
    """
    global _configured
    target_dir = log_dir or app_dir()
    log_path = target_dir / "autodraw.log"

    if _configured:
        return log_path

    root = logging.getLogger("autodraw")
    root.setLevel(level)
    root.propagate = False

    try:
        file_handler = RotatingFileHandler(
            log_path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(file_handler)
    except OSError:
        pass  # read-only home: keep running with stderr only

    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(stream_handler)

    _configured = True
    return log_path


def get_logger(name: str) -> logging.Logger:
    """Returns a namespaced child logger, configuring logging on first use."""
    setup_logging()
    return logging.getLogger(f"autodraw.{name}")
