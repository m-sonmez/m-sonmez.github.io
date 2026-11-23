"""Dönen dosya günlüğü (rotating logger) kurulumu — qtp.log (1 MB × 3) ve canlı stderr tanılama."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILENAME = "qtp.log"
MAX_LOG_BYTES = 1_048_576
BACKUP_COUNT = 3
LOGGER_NAME = "qtp"

_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


class _DynamicStderrHandler(logging.StreamHandler):
    """Her kayıtta güncel sys.stderr akışına yazan ve satır bazında boşaltan handler."""

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        target = sys.stderr
        if target is None:
            return
        self.stream = target
        super().emit(record)
        try:
            self.flush()
        except Exception:
            pass


def parse_log_level(level: str | None) -> int:
    """Metin günlük düzeyini logging sabitine çevirir."""
    key = (level or "info").strip().lower()
    return _LEVEL_MAP.get(key, logging.INFO)


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        logger.removeHandler(handler)


def _add_stderr_handler(logger: logging.Logger, verbose: int, fallback_level: int = logging.INFO) -> int:
    stderr_level = logging.DEBUG if verbose >= 2 else (logging.INFO if verbose == 1 else fallback_level)
    stderr_handler = _DynamicStderrHandler()
    stderr_handler.setLevel(stderr_level)
    stderr_handler.setFormatter(logging.Formatter(fmt="[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(stderr_handler)
    return stderr_level


def setup_logging(
    log_dir: str | Path,
    level: str = "info",
    *,
    console: bool = False,
    verbose: int = 0,
) -> logging.Logger:
    """
    Dönen dosya günlüğünü yapılandırır (`qtp.log`, 1 MB × 3) ve isteğe bağlı canlı stderr akışı bağlar.
    Var olan handler'ları temizleyip günceller, böylece düzey değişiklikleri anında geçerli olur.
    """
    logger = logging.getLogger(LOGGER_NAME)
    file_level = parse_log_level(level)
    verbose_level = max(0, int(verbose))
    enable_stderr = bool(console) or verbose_level >= 1
    stderr_level = logging.DEBUG if verbose_level >= 2 else (logging.INFO if verbose_level == 1 else file_level)
    logger.setLevel(min(file_level, stderr_level) if enable_stderr else file_level)
    logger.propagate = False

    _clear_handlers(logger)

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
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    if enable_stderr:
        _add_stderr_handler(logger, verbose_level, fallback_level=file_level)

    return logger


def setup_ephemeral_logging(*, verbose: int = 0) -> logging.Logger:
    """Diske hiç dosya yazmadan yalnızca stderr (veya sessiz NullHandler) günlüğü kurar."""
    logger = logging.getLogger(LOGGER_NAME)
    verbose_level = max(0, int(verbose))
    logger.propagate = False
    _clear_handlers(logger)

    if verbose_level >= 1:
        lvl = _add_stderr_handler(logger, verbose_level, fallback_level=logging.INFO)
        logger.setLevel(lvl)
    else:
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.NullHandler())
    return logger


def attach_stderr_handler(*, verbose: int = 1) -> logging.Logger:
    """Etkin qtp kök logger'ına dosya handler'ını bozmadan canlı stderr akışı ekler/günceller."""
    logger = logging.getLogger(LOGGER_NAME)
    verbose_level = max(1, int(verbose))
    logger.propagate = False
    for handler in list(logger.handlers):
        if isinstance(handler, _DynamicStderrHandler):
            logger.removeHandler(handler)
    stderr_level = _add_stderr_handler(logger, verbose_level, fallback_level=logging.INFO)
    cur_level = logger.level if logger.level != logging.NOTSET else logging.INFO
    logger.setLevel(min(cur_level, stderr_level))
    return logger


def get_logger(submodule: str | None = None) -> logging.Logger:
    """QTP alt modülü için alt logger döndürür."""
    base = logging.getLogger(LOGGER_NAME)
    if not base.handlers:
        base.addHandler(logging.NullHandler())
    if submodule:
        return base.getChild(submodule)
    return base
