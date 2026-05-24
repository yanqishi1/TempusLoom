from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import threading
from typing import Optional

from .library_store import TempusLoomSettings


LOG_FILE_NAME = "tempusloom.log"


def configure_file_logging(settings: Optional[TempusLoomSettings] = None) -> Path:
    settings = settings or TempusLoomSettings()
    log_dir = settings.project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / LOG_FILE_NAME

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for handler in list(root_logger.handlers):
        if getattr(handler, "_tempusloom_file_handler", False):
            root_logger.removeHandler(handler)
            handler.close()

    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler._tempusloom_file_handler = True
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root_logger.addHandler(handler)
    install_exception_logging()
    logging.getLogger(__name__).info("TempusLoom logging initialized: %s", log_path)
    return log_path


def install_exception_logging() -> None:
    def excepthook(exc_type, exc_value, exc_traceback):
        logging.getLogger("tempusloom.unhandled").exception(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook

    if hasattr(threading, "excepthook"):
        def threading_excepthook(args):
            logging.getLogger("tempusloom.thread").exception(
                "Unhandled thread exception",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = threading_excepthook
