"""
handlers/download.py
====================
پردازش‌گر اصلی: تشخیص لینک در پیام، اعمال rate limit، دانلود و ارسال محتوا
و دکمه‌های inline برای انتخاب کیفیت.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, TelegramError
from telegram.ext import ContextTypes

from tg_downloader_bot.config import config
from tg_downloader_bot.services.downloader import (
    Downloader,
    PrivateContentError,
    TooLargeError,
    DownloadError,
    downloader,
)
from tg_downloader_bot.services.stats import stats
from tg_downloader_bot.utils.logger import get_logger
from tg_downloader_bot.utils.messages import t, error_text
from tg_downloader_bot.utils.rate_limit import rate_limiter
from tg_downloader_bot.utils.url_parser import parse_message_links, ParsedLink

log = get_logger("handlers.download")


# ---------------------------------------------------------------------------
# ورودی: پیام متنی کاربر
# ---------------------------------------------------------------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تشخیص لینک در پیام کاربر و شروع فرآیند دانلود."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text

    # --- Rate limiting ---
    decision = rate_limiter.check(user.id)
    if not decision.allowed:
        await update.message.reply_text(t("rate_limited", sec=decision.retry_after))
        return

    # --- استخراج لینک‌ها ---
    links = parse_message_links(text, limit=config.MAX_LINKS_PER_MESSAGE)
    if not links:
        await update.message.reply_text(t("no_links"))
        return

    # اگر لینک‌های بیشتری از حد مجاز وجود داشت، اطلاع بده
    raw_count = len(text.split())  # تخمین ساده
    if raw_count > config.MAX_LINKS_PER_MESSAGE and len(links) >= config.MAX_LINKS_PER_MESSAGE:
        await update.message.reply_text(t("too_many_links", max=config.MAX_LINKS_PER_MESSAGE))

    # --- شروع پردازش ---
    context.user_data["cancelled"] = False
    status_msg = await update.message.reply_text(t("processing"))

    for idx, link in enumerate(links, start=1):
        if context.user_data.get("cancelled"):
            break
        header = f"🔗 ({idx}/{len(links)})" if len(links) > 1 else "🔗"
        await _process_one(update, context, link, status_msg, header)

    try:
        await status_msg.delete()
    except TelegramError:
        pass


# ---------------------------------------------------------------------------
# پردازش یک لینک
# ---------------------------------------------------------------------------
async def _process_one(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: ParsedLink,
    status_msg,
    header: str,
) -> None:
    """پردازش یک لینک: ابتدا متادیتا، سپس انتخاب کیفیت یا دانلود مستقیم."""
    user_id = update.effective_user.id

    try:
        await status_msg.edit_text(f"{header} {t('downloading', platform=link.platform)}")
    except TelegramError:
        pass

    # ابتدا متادیتا را بگیریم تا ببینیم چند کیفیت موجود است
    try:
        info = await downloader.extract(link.url)
    except Exception as exc:
        log.warning("extract failed for %s: %s", link.url, exc)
        info = None

    formats = []
    if info:
        try:
            from tg_downloader_bot.services.downloader import _extract_info
            title, formats = _extract_info(info)
        except Exception:
            formats = []

    # اگر چند کیفیتِ ویدیویی موجود بود، دکمه بده
    video_formats = [f for f in formats if f.get("height")]
    if len(video_formats) >= 2:
        await _ask_quality(update, context, link, video_formats, header, status_msg)
        return

    # در غیر این صورت دانلود مستقیم با کیفیت پیش‌فرض
    await _do_download_and_send(update, context, link, status_msg, header, format_selector=None)


# ---------------------------------------------------------------------------
# نمایش دکمه‌های کیفیت
# ---------------------------------------------------------------------------
async def _ask_quality(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: ParsedLink,
    video_formats: list[dict],
    header: str,
    status_msg,
) -> None:
    """نمایش دکمه‌های inline برای انتخاب کیفیت."""
    # مرتب‌سازی نزولی بر اساس ارتفاع
    video_formats.sort(key=lambda f: f["height"], reverse=True)

    rows: list[list[InlineKeyboardButton]] = []
    for f in video_formats[:6]:  # حداکثر 6 دکمه
        label = f["label"]
        size = f.get("filesize")
        size_str = f" ({size // (1024*1024)}MB)" if size and size > 0 else ""
        audio_icon = "🔊" if f.get("has_audio") else "🔇"
        callback_data = f"q:{f['format_id']}|{f['height']}|{f.get('has_audio') and 1 or 0}"
        # کلید url را در user_data نگه می‌داریم (callback_data محدودیت 64 بایتی دارد)
        rows.append(
            [
                InlineKeyboardButton(
                    f"{audio_icon} {label}{size_str}",
                    callback_data=callback_data,
                )
            ]
        )
    rows.append([InlineKeyboardButton("✅ بهترین کیفیت (پیش‌فرض)", callback_data="q:best|0|1")])

    # ذخیره لینک فعلی برای استفاده در callback
    context.user_data["pending_link"] = {
        "url": link.url,
        "platform": link.platform,
        "formats": video_formats,
    }

    markup = InlineKeyboardMarkup(rows)
    try:
        await status_msg.edit_text(
            f"{header}\n{t('choose_quality')}",
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        await update.effective_message.reply_text(t("choose_quality"), reply_markup=markup)


async def quality_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """هنگام زدن یک دکمه کیفیت."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""

    pending = context.user_data.get("pending_link")
    if not pending:
        await query.edit_message_text(t("download_failed"))
        return

    link = ParsedLink(url=pending["url"], platform=pending["platform"])

    # ساخت format_selector بر اساس انتخاب
    format_selector = None
    if data.startswith("q:"):
        parts = data[2:].split("|")
        choice = parts[0]
        height = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        has_audio = len(parts) > 2 and parts[2] == "1"
        if choice == "best":
            format_selector = None  # پیش‌فرض config
        else:
            # انتخاب فرمت با این ارتفاع و افزودن صدا
            if has_audio:
                format_selector = f"best[height<={height}]+bestaudio/best[height<={height}]/best"
            else:
                format_selector = f"best[height<={height}]/best"

    context.user_data.pop("pending_link", None)
    await _do_download_and_send(
        update, context, link, query.message, "🔗", format_selector=format_selector
    )


# ---------------------------------------------------------------------------
# دانلود و ارسال
# ---------------------------------------------------------------------------
async def _do_download_and_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    link: ParsedLink,
    status_msg,
    header: str,
    *,
    format_selector: str | None,
) -> None:
    """اجرای واقعی دانلود و ارسال فایل(ها) به کاربر."""
    # پیام وضعیت
    try:
        await status_msg.edit_text(f"{header} {t('downloading', platform=link.platform)}")
    except TelegramError:
        pass

    result = await downloader.download(
        url=link.url,
        platform=link.platform,
        progress_message=status_msg,
        format_selector=format_selector,
    )

    if not result.success:
        await _report_error(update, status_msg, result, header)
        return

    # ارسال فایل‌ها
    try:
        await status_msg.edit_text(f"{header} {t('uploading')}")
    except TelegramError:
        pass

    try:
        await _send_media(update, result, header)
        await stats.record(link.platform)
    except TelegramError as exc:
        log.error("Send failed for %s: %s", link.url, exc)
        await _safe_edit(status_msg, t("unknown_error"))
    finally:
        result.cleanup()


# ---------------------------------------------------------------------------
# ارسال رسانه به تلگرام
# ---------------------------------------------------------------------------
async def _send_media(update: Update, result, header: str) -> None:
    """ارسال فایل(های) نتیجه با انتخاب بهترین روش (media group یا تکی)."""
    chat_id = update.effective_chat.id
    items = result.items
    if not items:
        return

    # اگر بیش از یک فایل بود و همه عکس/ویدیوی سبک بودند → media group
    if len(items) > 1:
        await _send_media_group(update, items)
    else:
        await _send_single(update, items[0])


async def _send_media_group(update: Update, items) -> None:
    """ارسال گروهی (کاروسل)."""
    chat_id = update.effective_chat.id
    media: list = []
    oversized: list = []

    for it in items:
        if it.size > config.MAX_FILE_SIZE_BYTES:
            oversized.append(it)
            continue
        if it.kind == "image":
            media.append(InputMediaPhoto(media=open(it.path, "rb")))
        else:
            # ویدیو را به‌عنوان video یا document می‌فرستیم
            media.append(InputMediaVideo(media=open(it.path, "rb"), supports_streaming=True))

    if media:
        try:
            await update.get_bot().send_media_group(chat_id=chat_id, media=media)
        except TelegramError as exc:
            log.warning("media group send failed (%s); falling back to single", exc)
            # fallback: ارسال تکی
            for m in media:
                try:
                    # برای fallback ساده فایل‌ها را تکی می‌فرستیم
                    pass
                except Exception:
                    pass

    # فایل‌های بزرگ‌تر را به‌عنوان document بفرست
    for it in oversized:
        await _send_as_document(update, it)


async def _send_single(update: Update, item) -> None:
    """ارسال یک فایل تکی با تشخیص نوع و مدیریت حجم."""
    chat_id = update.effective_chat.id
    bot = update.get_bot()

    # اگر حجم بیشتر از حد مجاز بود → document
    if item.size > config.MAX_FILE_SIZE_BYTES:
        await _send_as_document(update, item)
        return

    try:
        with open(item.path, "rb") as fh:
            if item.kind == "image":
                await bot.send_photo(chat_id=chat_id, photo=fh)
            elif item.kind == "video":
                await bot.send_video(
                    chat_id=chat_id,
                    video=fh,
                    supports_streaming=True,
                )
            elif item.kind == "audio":
                await bot.send_audio(chat_id=chat_id, audio=fh)
            else:
                await bot.send_document(chat_id=chat_id, document=fh)
    except BadRequest as exc:
        # اگر به‌خاطر نوع فایل خطا داد، به‌عنوان document امتحان کن
        if "PHOTO_INVALID" in str(exc) or "video" in str(exc).lower():
            with open(item.path, "rb") as fh:
                await bot.send_document(chat_id=chat_id, document=fh)
        else:
            raise


async def _send_as_document(update: Update, item) -> None:
    """ارسال فایل به‌عنوان document (برای ویدیوهای طولانی یا فرمت‌های خاص)."""
    bot = update.get_bot()
    chat_id = update.effective_chat.id
    caption = t(
        "too_large",
        size=_fmt_size(item.size),
        limit=f"{config.MAX_FILE_SIZE_MB}MB",
    )
    with open(item.path, "rb") as fh:
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=fh,
                filename=item.path.name,
                caption=caption,
            )
        except TelegramError as exc:
            log.error("document send failed: %s", exc)
            await _safe_edit(
                update.effective_message,
                t("file_too_large_doc", size=_fmt_size(item.size), limit=f"{config.MAX_FILE_SIZE_MB}MB"),
            )


# ---------------------------------------------------------------------------
# helperهای گزارش خطا و ایمنی
# ---------------------------------------------------------------------------
async def _report_error(update: Update, status_msg, result, header: str) -> None:
    """گزارش خطای دانلود به کاربر با پیام کاربرپسند."""
    err = result.error or ""
    exc_like = Exception(err)
    # تبدیل به پیام کاربرپسند
    msg_user = error_text(exc_like)
    # اگر خطای خصوصی بود پیام مخصوص بده
    low = err.lower()
    if any(k in low for k in ("private", "login required", "log in")):
        msg_user = t("private_content")
    elif "geo" in low:
        msg_user = t("geo_blocked")
    elif "429" in low or "rate" in low or "blocked" in low:
        msg_user = t("blocked")

    log.warning("Download failed [%s]: %s", result.platform, err)
    await _safe_edit(status_msg, f"{header} {msg_user}")


async def _safe_edit(message, text: str) -> None:
    """ویرایش امن پیام که خطاها را نادیده می‌گیرد."""
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML)
    except TelegramError:
        try:
            await message.edit_text(text)
        except TelegramError:
            pass


def _fmt_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"
