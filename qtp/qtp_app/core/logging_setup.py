"""Dönen dosya günlüğü (rotating logger) kurulumu — qtp.log (1 MB × 3)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "qtp.log"
MAX_LOG_BYTES = 1_048_576  # 1 MB
BACKUP_COUNT = 3
LOGGER_NAME = "qtp"

_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def parse_log_level(level: str | None) -> int:
    """Metin günlük düzeyini logging sabitine çevirir."""
    key = (level or "info").strip().lower()
    return _LEVEL_MAP.get(key, logging.INFO)


def setup_logging(log_dir: str | Path, level: str = "info", *, console: bool = False) -> logging.Logger:
    """
    Dönen dosya günlüğünü yapılandırır (`qtp.log`, 1 MB × 3).
    Var olan handler'ları temizleyip günceller, böylece düzey değişiklikleri anında geçerli olur.
    """
    logger = logging.getLogger(LOGGER_NAME)
    numeric_level = parse_log_level(level)
    logger.setLevel(numeric_level)
    logger.propagate = False

    for handler in list(logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    target_dir = Path(log_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        log_path = target_dir / LOG_FILENAME
        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        # Günlük klasörü salt-okunursa sessizce stderr/NullHandler'a düş
        logger.addHandler(logging.NullHandler())

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(numeric_level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def get_logger(submodule: str | None = None) -> logging.Logger:
    """QTP alt modülü için alt logger döndürür."""
    base = logging.getLogger(LOGGER_NAME)
    if not base.handlers:
        base.addHandler(logging.NullHandler())
    if submodule:
        return base.getChild(submodule)
    return base
