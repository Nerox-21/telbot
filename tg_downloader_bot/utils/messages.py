"""
utils/messages.py
=================
قالب‌بندی پیام‌های کاربرپسند و ایموجی برای پاسخ‌های ربات (دوزبانه fa/en).
"""
from __future__ import annotations

from tg_downloader_bot.config import config

_FA = {
    "start": (
        "👋 سلام {name}!\n\n"
        "🎬 <b>به ربات دانلودر رسانه خوش آمدید.</b>\n\n"
        "فقط لینک پست/ویدیو را بفرست تا آن را برایت دانلود و ارسال کنم. "
        "پلتفرم‌های پشتیبانی‌شده:\n\n"
        "📸 Instagram (پست، ریلز، استوری، هایلایت، کاروسل، IGTV)\n"
        "🎵 TikTok\n"
        "🐦 Twitter / X\n"
        "▶️ YouTube (Shorts/ویدیو)\n"
        "📌 Pinterest\n"
        "🌐 و بسیاری دیگر...\n\n"
        "برای راهنمایی /help را بفرست."
    ),
    "help": (
        "📖 <b>راهنمای استفاده</b>\n\n"
        "1) لینک محتوا را در یک پیام بفرست.\n"
        "2) در صورت تشخیص، دکمه‌های انتخاب کیفیت نمایش داده می‌شود.\n"
        "3) برای چند لینک، می‌توانی همه را در یک پیام بفرستی "
        "(حداکثر {max_links} لینک).\n\n"
        "🛡 محدودیت‌ها:\n"
        "• حداکثر حجم فایل: {max_mb} مگابایت\n"
        "• نرخ درخواست: {rate_max} درخواست در {rate_win} ثانیه\n\n"
        "🔧 دستورات:\n"
        "/start — معرفی ربات\n"
        "/help — همین راهنما\n"
        "/stats — آمار دانلودهای امروز\n"
        "/cancel — لغو عملیات جاری"
    ),
    "processing": "🔎 در حال بررسی لینک…",
    "downloading": "⬇️ شروع دانلود از {platform}…",
    "uploading": "⏫ در حال ارسال به تلگرام…",
    "done": "✅ تمام شد!",
    "no_links": "❌ هیچ لینک معتبری در پیام شما پیدا نشد.",
    "too_many_links": "⚠️ بیش از حد مجاز لینک! فقط {max} لینک پردازش شد.",
    "rate_limited": (
        "🐢 دست‌ت سریع است! لطفاً {sec:.0f} ثانیه دیگر دوباره امتحان کن."
    ),
    "invalid_url": "❌ لینک نامعتبر است.",
    "private_content": "🔒 این محتوا خصوصی است یا نیاز به ورود دارد.",
    "too_large": (
        "📦 حجم فایل ({size}) از حد مجاز ({limit}) بیشتر است. "
        "به‌صورت Document ارسال شد."
    ),
    "file_too_large_doc": "📦 حجم فایل ({size}) از حد مجاد ({limit}) بیشتر است.",
    "download_failed": "❌ دانلود ناموفق بود. بعداً دوباره تلاش کنید.",
    "geo_blocked": "🌍 این محتوا در دسترس نیست (محدودیت جغرافیایی).",
    "blocked": "🚫 پلتفرم درخواست را مسدود کرد. بعداً دوباره تلاش کنید.",
    "unknown_error": "⚠️ خطای ناشناخته‌ای رخ داد. ادمین مطلع شد.",
    "cancelled": "🚫 عملیات لغو شد.",
    "stats": (
        "📊 <b>آمار دانلود</b>\n\n"
        "امروز: {today}\n"
        "کل: {total}\n"
        "بر اساس پلتفرم:\n{by_platform}"
    ),
    "choose_quality": "🎬 کیفیت را انتخاب کنید:",
    "no_audio": "🔇 این ویدیو صدا ندارد (یا صدا جداگانه است).",
    "carousel_header": "🖼 کاروسل شامل {n} مورد:",
}

_EN = {
    "start": (
        "👋 Hi {name}!\n\n"
        "🎬 <b>Welcome to the Media Downloader Bot.</b>\n\n"
        "Just send a link to a post/video and I'll download & send it. "
        "Supported platforms:\n\n"
        "📸 Instagram, 🎵 TikTok, 🐦 Twitter/X, ▶️ YouTube, 📌 Pinterest, and more.\n\n"
        "Type /help for more."
    ),
    "help": (
        "📖 <b>Help</b>\n\n"
        "1) Send a content link.\n"
        "2) If detected, quality buttons will appear.\n"
        "3) You can send up to {max_links} links in one message.\n\n"
        "🛡 Limits:\n"
        "• Max file size: {max_mb} MB\n"
        "• Rate: {rate_max} requests per {rate_win}s\n\n"
        "🔧 Commands: /start /help /stats /cancel"
    ),
    "processing": "🔎 Checking link…",
    "downloading": "⬇️ Starting download from {platform}…",
    "uploading": "⏫ Uploading to Telegram…",
    "done": "✅ Done!",
    "no_links": "❌ No valid link found in your message.",
    "too_many_links": "⚠️ Too many links! Only {max} processed.",
    "rate_limited": "🐢 Slow down! Try again in {sec:.0f}s.",
    "invalid_url": "❌ Invalid link.",
    "private_content": "🔒 This content is private or requires login.",
    "too_large": "📦 File ({size}) exceeds limit ({limit}). Sent as document.",
    "file_too_large_doc": "📦 File ({size}) exceeds limit ({limit}).",
    "download_failed": "❌ Download failed. Try again later.",
    "geo_blocked": "🌍 Content unavailable (geo-blocked).",
    "blocked": "🚫 Platform blocked the request. Try later.",
    "unknown_error": "⚠️ An unknown error occurred. Admin notified.",
    "cancelled": "🚫 Operation cancelled.",
    "stats": (
        "📊 <b>Stats</b>\n\nToday: {today}\nTotal: {total}\nBy platform:\n{by_platform}"
    ),
    "choose_quality": "🎬 Choose quality:",
    "no_audio": "🔇 This video has no audio (or audio is separate).",
    "carousel_header": "🖼 Carousel of {n} items:",
}


def _dict() -> dict:
    return _FA if config.BOT_LANG == "fa" else _EN


def t(key: str, **kwargs) -> str:
    """ترجمه و قالب‌بندی یک کلید پیام."""
    table = _dict()
    text = table.get(key, key)
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        return text


def error_text(exc: Exception) -> str:
    """تبدیل استثناهای رایج به پیام کاربرپسند."""
    msg = str(exc).lower()
    if any(k in msg for k in ("private", "login required", "log in", "nsfw")):
        return t("private_content")
    if any(k in msg for k in ("geo", "not available in your country")):
        return t("geo_blocked")
    if any(k in msg for k in ("429", "rate", "too many request")):
        return t("blocked")
    if "http error 404" in msg or "not found" in msg:
        return t("invalid_url")
    return t("download_failed")
