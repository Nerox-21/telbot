"""
utils/files.py
==============
مدیریت فایل‌های موقت دانلود، پاک‌سازی امن و کارهای جانبی فایل.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from tg_downloader_bot.config import DOWNLOAD_DIR
from tg_downloader_bot.utils.logger import get_logger

log = get_logger("files")


def make_temp_dir(prefix: str = "dl_") -> Path:
    """ساخت یک پوشه موقت یکتا برای هر دانلود."""
    tmp = Path(tempfile.mkdtemp(prefix=prefix, dir=str(DOWNLOAD_DIR)))
    log.debug("Created temp dir: %s", tmp)
    return tmp


def cleanup_path(path: Path) -> None:
    """حذف امن فایل یا پوشه. خطاها را لاگ و نادیده می‌گیرد."""
    try:
        if path is None or not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        log.debug("Cleaned up: %s", path)
    except Exception as exc:  # pragma: no cover
        log.warning("Cleanup failed for %s: %s", path, exc)


def cleanup_many(paths: list[Path]) -> int:
    """پاک‌سازی چند مسیر و بازگشت تعداد پاک‌شده‌ها."""
    count = 0
    for p in paths:
        if p and Path(p).exists():
            cleanup_path(Path(p))
            count += 1
    return count


@contextmanager
def temp_download_dir(prefix: str = "dl_") -> Iterator[Path]:
    """Context manager که پوشه موقت را در پایان (حتی در صورت خطا) پاک می‌کند.

    استفاده:
        with temp_download_dir() as d:
            ...  # کار با d
    """
    tmp = make_temp_dir(prefix=prefix)
    try:
        yield tmp
    finally:
        cleanup_path(tmp)


def get_file_size(path: Path) -> int:
    """اندازه فایل به بایت؛ اگر نبود صفر."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def purge_old_downloads(max_age_seconds: int = 3600) -> int:
    """پاک‌سازی فایل/پوشه‌های قدیمی‌تر از max_age_seconds داخل DOWNLOAD_DIR.

    مناسب اجرای دوره‌ای برای رهاسازی فایل‌های فراموش‌شده.
    """
    now = time.time()
    removed = 0
    for entry in DOWNLOAD_DIR.iterdir():
        try:
            mtime = entry.stat().st_mtime
            if now - mtime > max_age_seconds:
                cleanup_path(entry)
                removed += 1
        except Exception:  # pragma: no cover
            continue
    if removed:
        log.info("Purged %d old entries from download dir", removed)
    return removed
