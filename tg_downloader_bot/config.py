"""
config.py
=========
تنظیمات مرکزی ربات. تمام مقادیر حساس از متغیرهای محیطی (فایل .env)
خوانده می‌شوند و در صورت نبود مقدار، از مقادیر پیش‌فرض امن استفاده می‌شود.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# بارگذاری فایل .env در صورت وجود
load_dotenv()

# ---------------------------------------------------------------------------
# مسیرهای پروژه
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
LOGS_DIR: Path = BASE_DIR / "logs"
DOWNLOAD_DIR: Path = BASE_DIR / "downloads"

for _d in (DATA_DIR, LOGS_DIR, DOWNLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _get_bool(key: str, default: bool = False) -> bool:
    """تبدیل رشته محیطی به boolean به‌صورت امن."""
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass
class Config:
    """کانتینر تایپ‌پذیرِ تمام تنظیمات ربات."""

    # --- تلگرام ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # --- ادمین‌ها (لیست آیدی عددی، جدا شده با کاما) ---
    ADMINS: list[int] = field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("ADMINS", "").split(",")
            if x.strip().isdigit()
        ]
    )

    # --- محدودیت‌ها ---
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    MAX_LINKS_PER_MESSAGE: int = int(os.getenv("MAX_LINKS_PER_MESSAGE", "5"))
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))

    # --- Rate Limiting ---
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # ثانیه
    RATE_LIMIT_MAX: int = int(os.getenv("RATE_LIMIT_MAX", "10"))  # تعداد در آن پنجره

    # --- پراکسی (اختیاری) ---
    # مثال: socks5://user:pass@127.0.0.1:1080  یا  http://127.0.0.1:8080
    PROXY_URL: str = os.getenv("PROXY_URL", "")
    USE_PROXY: bool = _get_bool("USE_PROXY", False)

    # --- yt-dlp ---
    YTDLP_FORMAT: str = os.getenv(
        "YTDLP_FORMAT",
        # اولویت: بهترین کیفیت ویدیو+صدا که 50MB نشود، وگرنه بهترین عمومی
        "bestvideo*+bestaudio/best",
    )
    YTDLP_COOKIEFILE: str = os.getenv("YTDLP_COOKIEFILE", "")
    YTDLP_RETRIES: int = int(os.getenv("YTDLP_RETRIES", "3"))

    # --- پنل‌ها/توکن‌های پلتفرم‌ها (اختیاری، برای دسترسی به محتوای خصوصی) ---
    INSTAGRAM_COOKIE: str = os.getenv("INSTAGRAM_COOKIE", "")  # رشته کوکی مرورگر

    # --- دیتابیس آمار ---
    STATS_DB: Path = DATA_DIR / "stats.json"

    # --- ظاهر و پیام‌ها ---
    BOT_NAME: str = os.getenv("BOT_NAME", "📥 Media Downloader")
    BOT_LANG: str = os.getenv("BOT_LANG", "fa")  # fa | en

    # --- لاگ ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMINS


config = Config()
