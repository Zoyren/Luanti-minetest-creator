import logging
import sys
from pathlib import Path
from typing import Callable, List


class UILogHandler(logging.Handler):
    """Gestionnaire de logs redirigeant les messages vers les composants UI abonnés."""

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: List[Callable[[str, str], None]] = []

    def add_callback(self, callback: Callable[[str, str], None]) -> None:
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        level = record.levelname
        for callback in self._callbacks:
            try:
                callback(level, msg)
            except Exception:
                pass


_ui_handler = UILogHandler()
_ui_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))


def setup_logger(log_dir: Path) -> logging.Logger:
    """Configure le système de journalisation global (Fichier + Console + UI)."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "lcs.log"

    logger = logging.getLogger("LuantiCreatorStudio")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(message)s")
        )

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.addHandler(_ui_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("LuantiCreatorStudio")


def register_ui_log_listener(callback: Callable[[str, str], None]) -> None:
    _ui_handler.add_callback(callback)