import os
import re
import logging
import requests
import instaloader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ─────────────────────────────────────────
#  تنظیمات
# ─────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8634441121:AAGgnPJSphEihGPTkgYAOduOiQS2zlotKp4")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

L = instaloader.Instaloader(
    download_video_thumbnails=False,
    save_metadata=False,
    download_geotags=False,
    download_comments=False,
    post_metadata_txt_pattern="",
    quiet=True,
)

# ─────────────────────────────────────────
#  ابزار
# ─────────────────────────────────────────
INSTAGRAM_REGEX = re.compile(
    r"(https?://)?(www\.)?instagram\.com/(p|reel|tv)/([A-Za-z0-9_\-]+)"
)

def extract_shortcode(url: str) -> str | None:
    m = INSTAGRAM_REGEX.search(url)
    return m.group(4) if m else None

def cleanup(directory: str):
    """پاک‌کردن فایل‌های موقت"""
    for f in os.listdir(directory):
        path = os.path.join(directory, f)
        try:
            os.remove(path)
        except Exception:
            pass
    try:
        os.rmdir(directory)
    except Exception:
        pass

# ─────────────────────────────────────────
#  هندلرها
# ─────────────────────────────────────────
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
        "• فقط پست‌های عمومی قابل دانلوده\n"
        "• برای پست‌های چند رسانه‌ای (carousel) همه فایل‌ها فرستاده می‌شن\n\n"
        "📌 دستورات:\n"
        "/start – شروع\n"
        "/help  – راهنما"
    )
    await update.message.reply_text(text)

async def handle_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    shortcode = extract_shortcode(url)

    if not shortcode:
        await update.message.reply_text("❌ لینک اینستاگرام معتبر نیست. لطفاً یه لینک درست بفرست.")
        return

    msg = await update.message.reply_text("⏳ در حال دانلود...")

    tmp_dir = f"ig_tmp_{shortcode}"
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)

        # پست چند رسانه‌ای
        if post.typename == "GraphSidecar":
            nodes = list(post.get_sidecar_nodes())
            await msg.edit_text(f"⏳ {len(nodes)} فایل پیدا شد، در حال ارسال...")
            for i, node in enumerate(nodes, 1):
                media_url = node.video_url if node.is_video else node.display_url
                data = requests.get(media_url, timeout=30).content
                path = os.path.join(tmp_dir, f"media_{i}.{'mp4' if node.is_video else 'jpg'}")
                with open(path, "wb") as f:
                    f.write(data)
                with open(path, "rb") as f:
                    if node.is_video:
                        await update.message.reply_video(f, caption=f"🎬 ویدیو {i} از {len(nodes)}")
                    else:
                        await update.message.reply_photo(f, caption=f"📸 عکس {i} از {len(nodes)}")

        # ویدیو / ریل
        elif post.is_video:
            data = requests.get(post.video_url, timeout=60).content
            path = os.path.join(tmp_dir, "video.mp4")
            with open(path, "wb") as f:
                f.write(data)
            caption = f"🎬 {post.caption[:200] if post.caption else ''}"
            with open(path, "rb") as f:
                await update.message.reply_video(f, caption=caption)

        # عکس تکی
        else:
            data = requests.get(post.url, timeout=30).content
            path = os.path.join(tmp_dir, "photo.jpg")
            with open(path, "wb") as f:
                f.write(data)
            caption = f"📸 {post.caption[:200] if post.caption else ''}"
            with open(path, "rb") as f:
                await update.message.reply_photo(f, caption=caption)

        await msg.delete()

    except instaloader.exceptions.LoginRequiredException:
        await msg.edit_text("🔒 این پست خصوصی‌ه یا نیاز به لاگین داره. فقط پست‌های عمومی رو می‌تونم دانلود کنم.")
    except instaloader.exceptions.InstaloaderException as e:
        logger.error(f"Instaloader error: {e}")
        await msg.edit_text("❌ خطا در دانلود. مطمئن شو لینک درسته و پست عمومیه.")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        await msg.edit_text("❌ خطا در اتصال به اینستاگرام. دوباره امتحان کن.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await msg.edit_text("❌ یه خطای غیرمنتظره پیش اومد. دوباره امتحان کن.")
    finally:
        cleanup(tmp_dir)

# ─────────────────────────────────────────
#  اجرا
# ─────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    logger.info("🤖 بات شروع به کار کرد...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
