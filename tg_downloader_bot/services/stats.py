"""
services/stats.py
=================
ذخیره و بازیابی آمار دانلود در یک فایل JSON ساده (بدون وابستگی خارجی).
امن برای دسترسی هم‌زمان از طریق asyncio.Lock.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

from tg_downloader_bot.config import config
from tg_downloader_bot.utils.logger import get_logger

log = get_logger("stats")


class StatsStore:
    """ذخیره‌گاه آمار با ساختار:

    {
        "total": int,
        "by_platform": {"instagram": N, ...},
        "by_day": {"2026-06-26": N, ...}
    }
    """

    def __init__(self, path: Path | None = None):
        self.path = path or config.STATS_DB
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = self._load()

    # ----- بارگذاری/ذخیره -----
    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"total": 0, "by_platform": {}, "by_day": {}}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("total", 0)
            data.setdefault("by_platform", {})
            data.setdefault("by_day", {})
            return data
        except Exception as exc:
            log.warning("Failed to load stats (%s); starting fresh.", exc)
            return {"total": 0, "by_platform": {}, "by_day": {}}

    def _save(self) -> None:
        try:
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            tmp.replace(self.path)
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to save stats: %s", exc)

    # ----- API عمومی -----
    async def record(self, platform: str) -> None:
        async with self._lock:
            self._data["total"] = int(self._data.get("total", 0)) + 1
            bp = self._data["by_platform"]
            bp[platform] = bp.get(platform, 0) + 1
            today = date.today().isoformat()
            bd = self._data["by_day"]
            bd[today] = bd.get(today, 0) + 1
            self._save()

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            # کپی سطحی برای جلوگیری از تغییر بیرونی
            return {
                "total": self._data.get("total", 0),
                "today": self._data.get("by_day", {}).get(date.today().isoformat(), 0),
                "by_platform": dict(self._data.get("by_platform", {})),
            }


# نمونه سراسری
stats = StatsStore()
