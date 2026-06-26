# 📥 Telegram Media Downloader Bot

ربات تلگرامی قدرتمند برای دانلود رسانه از اینستاگرام، تیک‌تاک، توییتر/ایکس، یوتیوب (Shorts)، پینترست و ده‌ها پلتفرم دیگر — مبتنی بر `yt-dlp`.

---

## ✨ امکانات

| قابلیت | توضیح |
|--------|-------|
| 🔗 تشخیص خودکار لینک | چند لینک در یک پیام پشتیبانی می‌شود |
| 🎬 چندرسانه‌ای | ویدیو، عکس، کاروسل (چند عکس/ویدیو)، IGTV، ریلز |
| 📊 انتخاب کیفیت | دکمه‌های inline برای انتخاب رزولوشن (در صورت وجود) |
| 📈 نوار پیشرفت | نمایش زنده‌ی درصد، سرعت و زمان باقی‌مانده |
| 🛡 Rate Limiting | جلوگیری از سوءاستفاده (Sliding-Window) |
| 📦 محدودیت حجم | ارسال خودکار به‌صورت Document برای فایل‌های بزرگ |
| 🧹 پاک‌سازی خودکار | فایل‌های موقت پس از ارسال حذف می‌شوند |
| 🔐 Proxy (اختیاری) | پشتیبانی از HTTP/SOCKS5 |
| 📋 آمار دانلود | دستور `/stats` برای مشاهده آمار |
| 🌐 دوزبانه | فارسی / انگلیسی (متغیر `BOT_LANG`) |

---

## 📁 ساختار پروژه

```
tg_downloader_bot/
├── tg_downloader_bot/
│   ├── __init__.py
│   ├── config.py              # تنظیمات + خواندن از .env
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── basic.py           # /start /help /stats /cancel
│   │   └── download.py        # پردازش لینک + دکمه کیفیت + ارسال
│   ├── services/
│   │   ├── __init__.py
│   │   ├── downloader.py      # موتور yt-dlp (async wrapper)
│   │   └── stats.py           # ذخیره آمار
│   └── utils/
│       ├── __init__.py
│       ├── logger.py          # لاگ چرخشی
│       ├── url_parser.py      # تشخیص لینک + پلتفرم
│       ├── rate_limit.py      # محدودیت نرخ
│       ├── progress.py        # نوار پیشرفت تلگرام
│       ├── files.py           # فایل موقت + پاک‌سازی
│       └── messages.py        # قالب پیام‌ها (fa/en)
├── data/                      # آمار (stats.json)
├── logs/                      # لاگ‌ها
├── downloads/                 # فایل‌های موقت
├── main.py                    # نقطه ورود
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🚀 نصب و اجرا

### ۱) پیش‌نیازها
- **Python 3.11+**
- **FFmpeg** (برای ادغام ویدیو/صدا yt-dlp). ویندوز: از [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) دانلود و به PATH اضافه کنید.

### ۲) نصب وابستگی‌ها

```bash
# ساخت محیط مجازی
python -m venv venv
source venv/Scripts/activate    # Git Bash روی ویندوز
# یا:  venv\Scripts\activate     # CMD/PowerShell

# نصب پکیج‌ها
pip install --upgrade pip
pip install -r requirements.txt
```

### ۳) پیکربندی

```bash
cp .env.example .env
```

سپس فایل `.env` را باز کنید و حداقل `BOT_TOKEN` را پر کنید:

```env
BOT_TOKEN=123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMINS=111111111               # آیدی عددی خودتان (از @userinfobot بگیرید)
```

> 💡 برای گرفتن توکن، به [@BotFather](https://t.me/BotFather) در تلگرام پیام `/newbot` بدهید.

### ۴) اجرا

```bash
python main.py
```

پس از اجرا، در تلگرام به ربات بروید و `/start` بزنید، سپس یک لینک بفرستید. 🎉

---

## 🔧 تنظیمات مهم (`.env`)

| متغیر | پیش‌فرض | توضیح |
|-------|---------|-------|
| `BOT_TOKEN` | — | توکن ربات (اجباری) |
| `ADMINS` | — | آیدی ادمین‌ها با کاما |
| `MAX_FILE_SIZE_MB` | `50` | سقف حجم فایل ارسالی |
| `MAX_LINKS_PER_MESSAGE` | `5` | حداکثر لینک در یک پیام |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | دانلود هم‌زمان |
| `RATE_LIMIT_WINDOW` | `60` | پنجره محدودیت (ثانیه) |
| `RATE_LIMIT_MAX` | `10` | حداکثر درخواست در پنجره |
| `USE_PROXY` | `false` | فعال‌سازی پراکسی |
| `PROXY_URL` | — | `http://...` یا `socks5://user:pass@host:port` |
| `YTDLP_COOKIEFILE` | — | مسیر فایل کوکی برای محتوای خصوصی |
| `INSTAGRAM_COOKIE` | — | رشته کوکی مرورگر اینستاگرام |
| `BOT_LANG` | `fa` | زبان پیام‌ها (`fa`/`en`) |

---

## 🔒 دسترسی به محتوای خصوصی (اختیاری)

برای دانلود استوری/هایلایت/پست خصوصی اینستاگرام باید کوکی مرورگر خود را به yt-dlp بدهید:

1. با اکستنشن [Get cookies.txt](https://chromewebstore.google.com/detail/get-cookiestxt/bgaddhkoddajcdgocglldofjekigamnk) در مرورگرِ لاگین‌شده، کوکی‌های اینستاگرام را export کنید.
2. فایل را در ریشه پروژه با نام `cookies.txt` ذخیره کنید.
3. در `.env`:
   ```env
   YTDLP_COOKIEFILE=cookies.txt
   ```

> ⚠️ از حساب اصلی استفاده نکنید؛ یک حساب فرعی بسازید تا بلاک نشود.

---

## 🧪 تست سریع

```bash
python main.py
# سپس در تلگرام:
/start
https://www.instagram.com/reel/XXXXXXXX/
https://youtu.be/XXXXXXXXXXX
```

---

## ❓ رفع اشکال

| مشکل | راه‌حل |
|------|-------|
| `BOT_TOKEN تنظیم نشده` | فایل `.env` را در ریشه پروژه بسازید و `BOT_TOKEN` را پر کنید |
| ویدیو بدون صدا می‌آید | FFmpeg نصب نیست؛ نصبش کنید و به PATH اضافه کنید |
| خطای `Private content` | کوکی اینستاگرام تنظیم کنید (بخش بالا) |
| تایم‌اوت/اتصال | `USE_PROXY=true` و `PROXY_URL` را تنظیم کنید |
| فایل بزرگ‌تر از ۵۰MB | به‌صورت Document ارسال می‌شود؛ یا `MAX_FILE_SIZE_MB` را کمتر کنید |

---

## 📜 لایسنس

MIT — آزاد برای استفاده و تغییر.

> توجه: این ابزار برای دانلود محتوای **عمومی** یا محتوایی که حق دسترسی به آن را دارید طراحی شده. مسئولیت نحوه استفاده بر عهده کاربر است.
