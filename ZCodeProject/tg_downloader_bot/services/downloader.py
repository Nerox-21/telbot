"""
services/downloader.py
======================
موتور دانلود اصلی بر پایه yt-dlp. عملیات دانلود در ThreadPool اجرا می‌شود
تا event loop تلگرام را مسدود نکند و نوار پیشرفت بتواند پیام را آپدیت کند.

خروجی هر دانلود یک DownloadResult شامل لیست فایل‌های دانلود‌شده است.
"""
from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from tg_downloader_bot.config import config
from tg_downloader_bot.utils.files import make_temp_dir, cleanup_path, get_file_size
from tg_downloader_bot.utils.logger import get_logger
from tg_downloader_bot.utils.progress import TelegramProgressHook

log = get_logger("downloader")


# ---------------------------------------------------------------------------
# استثناهای اختصاصی
# ---------------------------------------------------------------------------
class DownloadError(Exception):
    """خطای عمومی دانلود."""


class PrivateContentError(DownloadError):
    """محتوای خصوصی/نیازمند ورود."""


class TooLargeError(DownloadError):
    """فایل بزرگ‌تر از حد مجاز."""


# ---------------------------------------------------------------------------
# مدل‌های خروجی
# ---------------------------------------------------------------------------
@dataclass
class MediaItem:
    """یک فایل رسانه دانلودشده."""

    path: Path
    kind: str  # 'video' | 'image' | 'audio' | 'unknown'
    size: int
    title: str = ""
    url: str = ""

    @property
    def ext(self) -> str:
        return self.path.suffix.lower().lstrip(".")


@dataclass
class DownloadResult:
    """نتیجه کاملِ دانلود یک لینک."""

    success: bool
    platform: str
    url: str
    items: list[MediaItem] = field(default_factory=list)
    title: str = ""
    error: str = ""
    temp_dir: Path | None = None
    # فرمت‌های دردسترس برای انتخاب کیفیت (در صورت وجود)
    available_formats: list[dict] = field(default_factory=list)

    def cleanup(self) -> None:
        if self.temp_dir:
            cleanup_path(self.temp_dir)
            self.temp_dir = None


# ---------------------------------------------------------------------------
# helperهای داخلی
# ---------------------------------------------------------------------------
def _humanize_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num) < 1024.0:
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}TB"


def _build_ydl_opts(
    outdir: Path,
    *,
    progress_hook: Callable[[dict], None] | None = None,
    format_selector: str | None = None,
    max_filesize: int | None = None,
) -> dict[str, Any]:
    """ساخت dict تنظیمات yt-dlp.

    outtmpl طوری انتخاب شده که برای کاروسل‌ها و چندفایلی‌ها نیز یکتا باشد.
    """
    opts: dict[str, Any] = {
        # قالب نام‌گذاری یکتا برای جلوگیری از تداخل
        "outtmpl": str(outdir / "%(id)s.%(ext)s"),
        "noplaylist": False,  # برای کاروسل اینستاگرام و پلی‌لیست کوتاه
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": config.YTDLP_RETRIES,
        "fragment_retries": config.YTDLP_RETRIES,
        "concurrent_fragment_downloads": 4,
        "merge_output_format": "mp4",
        "postprocessors": [
            # ادغام ویدیو/صدا در صورت نیاز
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ],
        #.user-agent و هدرهای پیش‌فرض
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
        },
    }

    if format_selector:
        opts["format"] = format_selector
    else:
        opts["format"] = config.YTDLP_FORMAT

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    # پراکسی
    if config.USE_PROXY and config.PROXY_URL:
        opts["proxy"] = config.PROXY_URL

    # کوکی‌ها
    if config.YTDLP_COOKIEFILE:
        opts["cookiefile"] = config.YTDLP_COOKIEFILE
    elif config.INSTAGRAM_COOKIE:
        # تزریق کوکی اینستاگرام به‌صورت رشته‌ای
        opts["cookies"] = _cookie_string_to_dict(config.INSTAGRAM_COOKIE)

    # محدودیت حجم (در حد امکان با yt-dlp)
    if max_filesize:
        opts["max_filesize"] = max_filesize

    return opts


def _cookie_string_to_dict(cookie_str: str) -> dict[str, str]:
    """تبدیل رشته کوکی (key=val; key2=val2) به dict."""
    cookies: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def _classify(path: Path) -> str:
    """تشخیص نوع فایل از روی پسوند."""
    ext = path.suffix.lower().lstrip(".")
    if ext in {"mp4", "webm", "mkv", "mov", "avi", "m4v", "flv"}:
        return "video"
    if ext in {"jpg", "jpeg", "png", "webp", "gif", "bmp"}:
        return "image"
    if ext in {"mp3", "m4a", "aac", "ogg", "opus", "wav"}:
        return "audio"
    return "unknown"


def _collect_files(outdir: Path) -> list[MediaItem]:
    """جمع‌آوری فایل‌های نهایی (نه .part) به ترتیب نام."""
    items: list[MediaItem] = []
    for p in sorted(outdir.iterdir()):
        if p.is_dir():
            continue
        if p.suffix.lower() in {".part", ".ytdl", ".tmp"}:
            continue
        if p.name.startswith("."):
            continue
        items.append(
            MediaItem(
                path=p,
                kind=_classify(p),
                size=get_file_size(p),
                url="",
            )
        )
    return items


def _extract_info(info: dict) -> tuple[str, list[dict]]:
    """استخراج عنوان و لیست فرمت‌های موجود از info yt-dlp."""
    title = (
        info.get("title")
        or info.get(" webpage_url_domain", "").strip()
        or "media"
    )

    formats_raw = info.get("formats") or []
    seen_res: set[str] = set()
    out: list[dict] = []
    for f in reversed(formats_raw):  # از بهترین به بدترین
        # فقط فرمت‌های ویدیویی که audio هم دارند یا video-only با جفت
        if f.get("vcodec", "none") == "none":
            continue
        h = f.get("height")
        ext = f.get("ext", "mp4")
        if not h:
            continue
        label = f"{h}p"
        if label in seen_res:
            continue
        seen_res.add(label)
        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        acodec = f.get("acodec", "none")
        has_audio = acodec not in ("none", None)
        out.append(
            {
                "label": label,
                "height": int(h),
                "ext": ext,
                "filesize": int(filesize or 0),
                "format_id": f.get("format_id"),
                "has_audio": has_audio,
            }
        )
    return title, out


# ---------------------------------------------------------------------------
# موتور اصلی
# ---------------------------------------------------------------------------
class Downloader:
    """لایه‌ی ناهمگام (async) روی yt-dlp."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)
        log.info(
            "Downloader initialized (max_concurrent=%d, proxy=%s)",
            config.MAX_CONCURRENT_DOWNLOADS,
            bool(config.USE_PROXY and config.PROXY_URL),
        )

    # ----- استخراج متادیتا (بدون دانلود) -----
    async def extract(self, url: str) -> dict[str, Any]:
        """استخراج اطلاعات لینک بدون دانلود — برای انتخاب کیفیت."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_sync, url)

    def _extract_sync(self, url: str) -> dict[str, Any]:
        opts = _build_ydl_opts(Path("/tmp"))  # outtmpl استفاده نمی‌شود
        opts["skip_download"] = True
        opts["quiet"] = True
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    # ----- دانلود کامل -----
    async def download(
        self,
        url: str,
        platform: str,
        *,
        progress_message=None,
        format_selector: str | None = None,
    ) -> DownloadResult:
        """دانلود یک لینک و بازگرداندن DownloadResult.

        :param progress_message: پیام تلگرام برای آپدیت پیشرفت (اختیاری)
        :param format_selector: انتخابگر فرمت yt-dlp (مثلاً 'best[height<=720]')
        """
        async with self._semaphore:
            tmp = make_temp_dir(prefix=f"{platform}_")
            result = DownloadResult(
                success=False, platform=platform, url=url, temp_dir=tmp
            )
            hook = (
                TelegramProgressHook(progress_message, title=platform)
                if progress_message is not None
                else None
            )
            try:
                opts = _build_ydl_opts(
                    tmp,
                    progress_hook=hook,
                    format_selector=format_selector,
                    max_filesize=config.MAX_FILE_SIZE_BYTES,
                )
                loop = asyncio.get_running_loop()
                info = await loop.run_in_executor(
                    None, self._run_ydl, opts, url
                )
                items = _collect_files(tmp)
                if not items:
                    raise DownloadError("هیچ فایلی دانلود نشد (شاید محتوا خصوصی است).")

                # مرتب‌سازی: ویدیوها و عکس‌ها به ترتیب
                items.sort(key=lambda it: (it.kind != "video", it.path.name))
                result.items = items
                result.success = True
                if info:
                    title, fmts = _extract_info(info)
                    result.title = title
                    result.available_formats = fmts
                log.info(
                    "Downloaded %s -> %d file(s), total %s",
                    platform,
                    len(items),
                    _humanize_size(sum(i.size for i in items)),
                )
            except yt_dlp.utils.DownloadError as exc:
                result.error = str(exc)
                _classify_download_error(exc, result)
            except Exception as exc:  # pragma: no cover
                log.exception("Unexpected download error for %s", url)
                result.error = str(exc)
            return result

    def _run_ydl(self, opts: dict, url: str) -> dict | None:
        """اجراکننده همگام yt-dlp داخل thread."""
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                return ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError:
                raise
            except Exception:
                return None


def _classify_download_error(exc: Exception, result: DownloadResult) -> None:
    """تشخیص نوع خطا و تنظیم پرچم مناسب روی result.error."""
    msg = str(exc).lower()
    if any(k in msg for k in ("private", "login required", "log in", "nsfw")):
        raise PrivateContentError(str(exc)) from exc
    if "too large" in msg or "exceeds" in msg:
        raise TooLargeError(str(exc)) from exc
    # در غیر این صورت همان DownloadError عمومی
    raise DownloadError(str(exc)) from exc


# نمونه سراسری
downloader = Downloader()
