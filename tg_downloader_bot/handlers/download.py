"""
handlers/download.py
====================
پردازش‌گر اصلی: تشخیص لینک در پیام، اعمال rate limit، دانلود و ارسال محتوا.
"""
from __future__ import annotations

from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
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

    raw_count = len(text.split())
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
    """پردازش یک لینک و دانلود با بهترین کیفیت."""
    try:
        await status_msg.edit_text(f"{header} {t('downloading', platform=link.platform)}")
    except TelegramError:
        pass

    await _do_download_and_send(update, context, link, status_msg, header, format_selector=None)


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
    items = result.items
    if not items:
        return

    if len(items) > 1:
        await _send_media_group(update, items)
    else:
        await _send_single(update, items[0])


async def _send_media_group(update: Update, items) -> None:
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
            media.append(InputMediaVideo(media=open(it.path, "rb"), supports_streaming=True))

    if media:
        try:
            await update.get_bot().send_media_group(chat_id=chat_id, media=media)
        except TelegramError as exc:
            log.warning("media group send failed (%s); falling back to single", exc)

    for it in oversized:
        await _send_as_document(update, it)


async def _send_single(update: Update, item) -> None:
    chat_id = update.effective_chat.id
    bot = update.get_bot()

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
        if "PHOTO_INVALID" in str(exc) or "video" in str(exc).lower():
            with open(item.path, "rb") as fh:
                await bot.send_document(chat_id=chat_id, document=fh)
        else:
            raise


async def _send_as_document(update: Update, item) -> None:
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
    err = result.error or ""
    exc_like = Exception(err)
    msg_user = error_text(exc_like)
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
