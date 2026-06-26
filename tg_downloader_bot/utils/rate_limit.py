"""
utils/rate_limit.py
===================
Rate limiting ساده و سبک بر اساس الگوریتم Sliding-Window.
به‌ازای هر کاربر یک پنجره زمانی نگه می‌داریم و تعداد درخواست‌ها را محدود می‌کنیم.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

from tg_downloader_bot.config import config


@dataclass
class RateDecision:
    """نتیجه بررسی محدودیت نرخ."""

    allowed: bool
    remaining: int
    retry_after: float  # ثانیه تا آزاد شدن یک اسلات


class SlidingWindowRateLimiter:
    """محدودکننده نرخ با پنجره کشسان (Sliding Window).

    برای هر کلید (مثلاً user_id) یک deque از timestampها نگه می‌داریم.
    """

    def __init__(self, window: int, max_requests: int):
        self.window = window
        self.max_requests = max_requests
        self._buckets: dict[int, deque[float]] = defaultdict(deque)

    def check(self, key: int, *, now: float | None = None) -> RateDecision:
        t = time.monotonic() if now is None else now
        bucket = self._buckets[key]

        # حذف رکوردهای قدیمی خارج از پنجره
        cutoff = t - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) < self.max_requests:
            bucket.append(t)
            return RateDecision(
                allowed=True,
                remaining=self.max_requests - len(bucket),
                retry_after=0.0,
            )

        # محاسبه زمان باقی‌مانده تا آزاد شدن قدیمی‌ترین رکورد
        retry_after = bucket[0] + self.window - t
        return RateDecision(
            allowed=False,
            remaining=0,
            retry_after=max(retry_after, 0.0),
        )

    def reset(self, key: int) -> None:
        self._buckets.pop(key, None)


# نمونه سراسری، با مقادیر config
rate_limiter = SlidingWindowRateLimiter(
    window=config.RATE_LIMIT_WINDOW,
    max_requests=config.RATE_LIMIT_MAX,
)
