"""
utils/logger.py
===============
راه‌اندازی سیستم لاگ متمرکز. هم در کنسول و هم در فایل logs/bot.log.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from tg_downloader_bot.config import config, LOGS_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging() -> logging.Logger:
    """راه‌اندازی لاگر اصلی. فقط یک‌بار اجرا می‌شود."""
    global _initialized
    if _initialized:
        return logging.getLogger("tgdl")

    root = logging.getLogger("tgdl")
    root.setLevel(config.LOG_LEVEL)

    # جلوگیری از propagation مضاعف
    root.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- کنسول ---
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # --- فایل چرخشی (5MB × 3) ---
    file_handler = RotatingFileHandler(
        LOGS_DIR / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # کاهش نویز کتابخانه‌های third-party
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)

    _initialized = True
    root.info("Logging subsystem initialized — level=%s", config.LOG_LEVEL)
    return root


def get_logger(name: str) -> logging.Logger:
    """گرفتن یک لاگر فرزند از لاگر اصلی."""
    return logging.getLogger("tgdl").getChild(name)
