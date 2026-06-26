"""
main.py
=======
نقطه ورود ربات. راه‌اندازی Application تلگرام، ثبت handlerها، تنظیم پراکسی
و شروع polling طولانی‌مدت.
"""
from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from tg_downloader_bot.config import config
from tg_downloader_bot.utils.logger import setup_logging, get_logger
from tg_downloader_bot.utils.files import purge_old_downloads
from tg_downloader_bot.handlers.basic import (
    start_cmd,
    help_cmd,
    stats_cmd,
    cancel_cmd,
)
from tg_downloader_bot.handlers.download import (
    handle_message,
    quality_callback,
)

log = get_logger("main")


# ---------------------------------------------------------------------------
# مدیریت خطاهای گلوبال
# ---------------------------------------------------------------------------
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر خطای مرکزی — خطاها را لاگ و در صورت امکان به کاربر اطلاع می‌دهد."""
    log.error("Unhandled exception while handling update:", exc_info=context.error)
    # اطلاع به ادمین‌ها
    if config.ADMINS:
        err_text = f"⚠️ خطای غیرمنتظره:\n<code>{context.error}</code>"
        for admin_id in config.ADMINS:
            try:
                await context.bot.send_message(admin_id, err_text, parse_mode="HTML")
            except Exception:
                pass
    # اطلاع به کاربر
    if update and hasattr(update, "effective_message") and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید."
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# کارهای دوره‌ای
# ---------------------------------------------------------------------------
async def _periodic_cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """هر یک ساعت فایل‌های قدیمی دانلود را پاک می‌کند."""
    purge_old_downloads(max_age_seconds=3600)


# ---------------------------------------------------------------------------
# ساخت Application
# ---------------------------------------------------------------------------
def build_application() -> Application:
    """ساخت و پیکربندی Application تلگرام با handlerها."""
    if not config.BOT_TOKEN:
        log.error("BOT_TOKEN تنظیم نشده! فایل .env را پر کنید.")
        sys.exit(1)

    builder = ApplicationBuilder().token(config.BOT_TOKEN)

    # پراکسی
    if config.USE_PROXY and config.PROXY_URL:
        proxy = config.PROXY_URL
        log.info("Using proxy: %s", proxy)
        if proxy.startswith("socks"):
            builder = builder.proxy(proxy).get_updates_proxy(proxy)
        else:
            builder = builder.proxy(proxy).get_updates_proxy(proxy)

    app = builder.build()

    # ----- ثبت handlerها -----
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # callback کیفیت
    app.add_handler(CallbackQueryHandler(quality_callback, pattern=r"^q:"))

    # پیام‌های متنی که لینک دارند (هر پیامی که / نباشد)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.Regex(r"https?://"),
            handle_message,
        )
    )

    # خطای گلوبال
    app.add_error_handler(on_error)

    # کار دوره‌ای پاک‌سازی (هر ۱ ساعت)
    if app.job_queue is not None:
        app.job_queue.run_repeating(
            _periodic_cleanup, interval=3600, first=60, name="cleanup"
        )

    log.info("Application built with all handlers registered.")
    return app


# ---------------------------------------------------------------------------
# ورودی اصلی
# ---------------------------------------------------------------------------
async def post_init(app: Application) -> None:
    """اجرا پس از مقداردهی اولیه — بررسی اتصال به بات."""
    me = await app.bot.get_me()
    log.info("Connected as @%s (id=%s)", me.username, me.id)


def main() -> None:
    setup_logging()
    log.info("=== Starting Telegram Media Downloader Bot ===")
    log.info("Max file size: %d MB | Max links/msg: %d",
             config.MAX_FILE_SIZE_MB, config.MAX_LINKS_PER_MESSAGE)

    app = build_application()

    # مدیریت سیگنال برای خروج تمیز (پایتون روی ویندوز: محدودیت‌هایی دارد)
    app.run_polling(
        allowed_updates=None,
        poll_interval=2.0,
        timeout=30,
        drop_pending_updates=False,
        post_init=post_init,
    )


if __name__ == "__main__":
    main()
