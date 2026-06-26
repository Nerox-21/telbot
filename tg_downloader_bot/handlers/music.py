"""
handlers/music.py
=================
هندلر تشخیص آهنگ:
- کاربر لینک اینستاگرام/ویدیو می‌فرسته
- بات ویدیو رو دانلود می‌کنه
- آهنگ رو تشخیص میده
- نتیجه رو می‌فرسته
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from tg_downloader_bot.config import config
from tg_downloader_bot.services.downloader import downloader
from tg_downloader_bot.services.music_recognizer import recognize_from_file
from tg_downloader_bot.utils.logger import get_logger
from tg_downloader_bot.utils.url_parser import parse_message_links

log = get_logger("handlers.music")


async def handle_music_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    دستور /music یا /shazam - تشخیص آهنگ از لینک
    استفاده: /music https://instagram.com/reel/xxx
    """
    if not context.args:
        await update.message.reply_text(
            "🎵 لینک ویدیو رو بعد از دستور بفرست:\n"
            "<code>/music https://instagram.com/reel/xxx</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    url = context.args[0].strip()
    await _process_music_detection(update, context, url)


async def handle_music_from_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    وقتی کاربر لینک می‌فرسته، دکمه 'تشخیص آهنگ 🎵' نشون بده
    این هندلر باید بعد از handle_message در main.py ثبت بشه
    """
    pass  # این از طریق callback_query مدیریت میشه


async def music_detect_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """وقتی کاربر روی دکمه 'تشخیص آهنگ' کلیک می‌کنه"""
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    if not data.startswith("music:"):
        return

    url = data[6:]  # حذف پیشوند "music:"
    await _process_music_detection(update, context, url, status_msg=query.message)


async def _process_music_detection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    status_msg=None,
) -> None:
    """منطق اصلی دانلود و تشخیص آهنگ"""

    # تشخیص پلتفرم
    links = parse_message_links(url)
    if not links:
        msg = "❌ لینک معتبر نیست."
        if status_msg:
            await status_msg.edit_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    link = links[0]

    # پیام وضعیت
    if status_msg:
        try:
            await status_msg.edit_text("⬇️ در حال دانلود ویدیو برای تشخیص آهنگ...")
        except TelegramError:
            pass
    else:
        status_msg = await update.message.reply_text("⬇️ در حال دانلود ویدیو برای تشخیص آهنگ...")

    # دانلود ویدیو
    result = await downloader.download(
        url=link.url,
        platform=link.platform,
        progress_message=None,  # بدون نوار پیشرفت برای این حالت
    )

    if not result.success or not result.items:
        try:
            await status_msg.edit_text("❌ دانلود ناموفق بود. لینک رو بررسی کن.")
        except TelegramError:
            pass
        return

    # پیدا کردن فایل ویدیو/صوتی
    media_file = None
    for item in result.items:
        if item.kind in ("video", "audio"):
            media_file = item.path
            break

    if not media_file:
        media_file = result.items[0].path  # هر فایلی که بود

    try:
        await status_msg.edit_text("🎵 در حال تشخیص آهنگ...")
    except TelegramError:
        pass

    # تشخیص آهنگ
    recognition = await recognize_from_file(media_file)

    # ارسال نتیجه
    try:
        if recognition.found:
            msg_text = recognition.format_message()

            # اگر کاور داشت، با عکس بفرست
            if recognition.cover_url:
                try:
                    cover_data = requests.get(recognition.cover_url, timeout=10).content
                    await update.effective_message.reply_photo(
                        photo=cover_data,
                        caption=msg_text,
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    await update.effective_message.reply_text(
                        msg_text, parse_mode=ParseMode.HTML
                    )
            else:
                await update.effective_message.reply_text(
                    msg_text, parse_mode=ParseMode.HTML
                )

            try:
                await status_msg.delete()
            except TelegramError:
                pass
        else:
            await status_msg.edit_text(
                "🎵 آهنگی در این ویدیو تشخیص داده نشد.\n"
                "ممکنه ویدیو بی‌کلام باشه یا آهنگ خیلی کمرنگ باشه."
            )
    except TelegramError as e:
        log.error("Send music result error: %s", e)
    finally:
        result.cleanup()
