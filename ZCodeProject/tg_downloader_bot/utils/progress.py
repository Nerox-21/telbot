"""
utils/progress.py
=================
نمایش نوار پیشرفت دانلود به‌صورت زیبا و هوشمند ( throttling پیام تلگرام).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

try:
    import humanize
except Exception:  # pragma: no cover
    humanize = None


def _fmt_bytes(num: float) -> str:
    """فرمت‌بندی حجم به‌صورت خوانا."""
    if humanize is not None:
        return humanize.naturalsize(num, binary=False)
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"


def _build_bar(percent: float, width: int = 14) -> str:
    """ساخت یک نوار پیشرفت متنی: ▰▰▰▰▰▱▱▱▱▱ 50%"""
    filled = int(width * percent / 100)
    bar = "▰" * filled + "▱" * (width - filled)
    return f"{bar} {percent:.0f}%"


@dataclass
class ProgressState:
    """وضعیت لحظه‌ای یک دانلود."""

    downloaded: float = 0.0
    total: float = 0.0
    speed: float = 0.0
    eta: float = 0.0
    percent: float = 0.0
    last_text: str = ""

    def render(self, title: str = "دانلود") -> str:
        total_str = _fmt_bytes(self.total) if self.total else "؟"
        dl_str = _fmt_bytes(self.downloaded)
        speed_str = _fmt_bytes(self.speed) + "/s" if self.speed else "—"
        eta_str = (
            f"{int(self.eta)}ث"
            if self.eta and self.total and self.percent < 100
            else "—"
        )
        bar = _build_bar(self.percent)
        self.last_text = (
            f"📥 <b>{title}</b>\n\n"
            f"{bar}\n\n"
            f"💾 {dl_str} / {total_str}\n"
            f"⚡ سرعت: {speed_str}\n"
            f"⏳ زمان باقی‌مانده: {eta_str}"
        )
        return self.last_text


class TelegramProgressHook:
    """هوک پیشرفتِ سازگار با yt-dlp برای آپدیت پیام تلگرام به‌صورت throttled.

    yt-dlp با شروع، هنگام دانلود و در پایان، تابع هوک را فراخوانی می‌کند.
    """

    def __init__(self, update_message, title: str = "دانلود", min_interval: float = 1.5):
        """
        :param update_message: شیء پیام تلگرام (ContextTypes.DEFAULT_TYPE قابلیت edit_text دارد)
        :param title: عنوان نمایشی
        :param min_interval: حداقل فاصله (ثانیه) بین دو آپدیت پیام
        """
        self.message = update_message
        self.title = title
        self.min_interval = min_interval
        self.state = ProgressState()
        self._last_push: float = 0.0
        self._last_sent_text: str = ""

    def __call__(self, d: dict) -> None:
        """ورودیِ سازگار با yt-dlp hooks."""
        status = d.get("status")
        if status == "downloading":
            self.state.downloaded = float(d.get("downloaded_bytes") or 0)
            self.state.total = float(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
            self.state.speed = float(d.get("speed") or 0)
            self.state.eta = float(d.get("eta") or 0)
            if self.state.total:
                self.state.percent = self.state.downloaded / self.state.total * 100
            else:
                self.state.percent = 0
            self._maybe_push()
        elif status == "finished":
            self.state.percent = 100
            self.state.downloaded = float(d.get("downloaded_bytes") or self.state.downloaded)
            self.state.total = self.state.downloaded
            self._maybe_push(force=True, finished=True)

    def _maybe_push(self, *, force: bool = False, finished: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_push) < self.min_interval:
            return
        text = self.state.render(self.title)
        if text == self._last_sent_text and not finished:
            return
        self._last_push = now
        self._last_sent_text = text
        # ویرایش پیام به‌صورت ناهمگام-امن: صرفاً متد را فراخوانی می‌کنیم؛
        # اگر از داخل yt-dlp async نباشد، فراخوانی best-effort است.
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._safe_edit(text), loop
                )
            else:  # pragma: no cover
                loop.run_until_complete(self._safe_edit(text))
        except Exception:
            # در صورت بروز هر خطایی در آپدیت، بی‌سایمان نکنیم
            pass

    async def _safe_edit(self, text: str) -> None:
        try:
            await self.message.edit_text(text, parse_mode="HTML")
        except Exception:
            # "message is not modified" یا rate limit تلگرام → نادیده
            pass
