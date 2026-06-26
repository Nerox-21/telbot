import os
import re
import logging
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8634441121:AAGgnPJSphEihGPTkgYAOduOiQS2zlotKp4")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

INSTAGRAM_REGEX = re.compile(
    r"(https?://)?(www\.)?instagram\.com/(p|reel|tv)/([A-Za-z0-9_\-]+)"
)

def extract_shortcode(url: str) -> str | None:
    m = INSTAGRAM_REGEX.search(url)
    return m.group(4) if m else None

def get_media_info(url: str) -> dict | None:
    """استفاده از RapidAPI برای دریافت لینک مستقیم"""
    try:
        api_url = "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index"
        headers = {
            "x-rapidapi-host": "instagram-downloader-download-instagram-videos-stories.p.rapidapi.com",
            "x-rapidapi-key": os.environ.get("RAPIDAPI_KEY", "")
        }
        params = {"url": url}
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        data = response.json()
        return data
    except Exception as e:
        logger.error(f"API error: {e}")
        return None

def get_media_snapinsta(url: str):
    """استفاده از snapinsta به عنوان روش جایگزین"""
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        # گرفتن token
        r = session.get("https://snapinsta.app/", timeout=15)
        token_match = re.search(r'name="_token"\s+value="([^"]+)"', r.text)
        if not token_match:
            return None
        token = token_match.group(1)

        # ارسال لینک
        r2 = session.post(
            "https://snapinsta.app/action.php",
            data={"url": url, "_token": token, "q": url, "t": "media"},
            timeout=30
        )
        data = r2.json()
        return data
    except Exception as e:
        logger.error(f"Snapinsta error: {e}")
        return None

def get_direct_url_via_cobalt(url: str) -> str | None:
    """استفاده از cobalt.tools API"""
    try:
        r = requests.post(
            "https://api.cobalt.tools/",
            json={"url": url, "downloadMode": "auto"},
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            timeout=30
        )
        data = r.json()
        logger.info(f"Cobalt response: {data}")
        if data.get("status") in ("tunnel", "redirect", "stream"):
            return data.get("url")
        if data.get("status") == "picker":
            # چند رسانه‌ای
            return [item["url"] for item in data.get("picker", [])]
        return None
    except Exception as e:
        logger.error(f"Cobalt error: {e}")
        return None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 سلام!\n\n"
        "لینک پست، ریل یا IGTV اینستاگرام رو برام بفرست تا دانلود کنم 🎬📸\n\n"
        "مثال:\n"
        "https://www.instagram.com/p/XXXXXXXX/\n"
        "https://www.instagram.com/reel/XXXXXXXX/"
    )
    await update.message.reply_text(text)

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 راهنما:\n\n"
        "• لینک پست عکس یا ویدیو اینستاگرام رو بفرست\n"
        "• فقط پست‌های عمومی قابل دانلوده\n\n"
        "📌 دستورات:\n"
        "/start – شروع\n"
        "/help  – راهنما"
    )
    await update.message.reply_text(text)

async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    if not INSTAGRAM_REGEX.search(url):
        await update.message.reply_text("❌ لینک اینستاگرام معتبر نیست.")
        return

    msg = await update.message.reply_text("⏳ در حال دانلود...")

    try:
        result = get_direct_url_via_cobalt(url)

        if not result:
            await msg.edit_text("❌ خطا در دانلود. ممکنه پست خصوصی باشه یا لینک اشتباه.")
            return

        # چند رسانه‌ای
        if isinstance(result, list):
            await msg.edit_text(f"⏳ {len(result)} فایل پیدا شد، در حال ارسال...")
            for i, media_url in enumerate(result, 1):
                data = requests.get(media_url, timeout=60).content
                content_type = requests.head(media_url).headers.get("content-type", "")
                if "video" in content_type:
                    await update.message.reply_video(data, caption=f"🎬 {i} از {len(result)}")
                else:
                    await update.message.reply_photo(data, caption=f"📸 {i} از {len(result)}")
            await msg.delete()
            return

        # تک فایل - تشخیص نوع
        head = requests.head(result, timeout=15)
        content_type = head.headers.get("content-type", "")
        data = requests.get(result, timeout=60).content

        if "video" in content_type:
            await update.message.reply_video(data, caption="🎬")
        else:
            await update.message.reply_photo(data, caption="📸")

        await msg.delete()

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await msg.edit_text("❌ خطای غیرمنتظره. دوباره امتحان کن.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    logger.info("🤖 بات شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
