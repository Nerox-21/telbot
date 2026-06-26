"""
handlers/basic.py
=================
دستورات پایه: /start، /help، /stats و /cancel.
"""
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from tg_downloader_bot.config import config
from tg_downloader_bot.services.stats import stats
from tg_downloader_bot.utils.logger import get_logger
from tg_downloader_bot.utils.messages import t

log = get_logger("handlers.basic")


def _user_name(update: Update) -> str:
    u = update.effective_user
    if not u:
        return "دوست"
    return u.first_name or u.username or "دوست"


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به /start با پیام خوش‌آمد."""
    await update.message.reply_text(
        t("start", name=_user_name(update)),
        parse_mode=ParseMode.HTML,
    )
    log.info("User %s started the bot", update.effective_user.id)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ به /help."""
    await update.message.reply_text(
        t(
            "help",
            max_links=config.MAX_LINKS_PER_MESSAGE,
            max_mb=config.MAX_FILE_SIZE_MB,
            rate_max=config.RATE_LIMIT_MAX,
            rate_win=config.RATE_LIMIT_WINDOW,
        ),
        parse_mode=ParseMode.HTML,
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش آمار دانلود (فقط ادمین‌ها یا همه، بسته به ترجیح)."""
    snap = await stats.snapshot()
    bp = snap["by_platform"]
    if bp:
        by_platform = "\n".join(f"• {k}: {v}" for k, v in bp.items())
    else:
        by_platform = "• (هنوز داده‌ای ثبت نشده)"
    await update.message.reply_text(
        t(
            "stats",
            today=snap["today"],
            total=snap["total"],
            by_platform=by_platform,
        ),
        parse_mode=ParseMode.HTML,
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لغو هر عملیات جاری برای این کاربر (پاک‌سازی job_queue/user_data)."""
    uid = update.effective_user.id
    # لغو هر job فعال برای این کاربر
    current = context.user_data.get("current_jobs", [])
    for job in current:
        try:
            job.schedule_removal()
        except Exception:
            pass
    context.user_data["cancelled"] = True
    context.user_data["current_jobs"] = []
    await update.message.reply_text(t("cancelled"))
    log.info("User %s cancelled current operation", uid)
