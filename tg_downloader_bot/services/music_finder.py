"""
services/music_finder.py
========================
شناسایی آهنگ از فایل ویدیویی با استفاده از shazamio.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from shazamio import Shazam

from tg_downloader_bot.utils.logger import get_logger

log = get_logger("music_finder")


async def find_song(video_path: Path) -> dict | None:
    """
    از فایل ویدیویی آهنگ را شناسایی می‌کند.
    خروجی: دیکشنری با اطلاعات آهنگ یا None در صورت عدم شناسایی.
    """
    try:
        shazam = Shazam()
        result = await shazam.recognize(str(video_path))

        if not result or "track" not in result:
            return None

        track = result["track"]
        title = track.get("title", "نامشخص")
        artist = track.get("subtitle", "نامشخص")

        # لینک یوتیوب از بخش actions
        youtube_url = None
        for action in track.get("actions", []):
            if action.get("type") == "uri" and "youtube" in action.get("uri", ""):
                youtube_url = action["uri"]
                break

        # اگر لینک یوتیوب پیدا نشد از sections بگردیم
        if not youtube_url:
            for section in track.get("sections", []):
                for meta in section.get("metadata", []):
                    pass
                for action in section.get("actions", []):
                    if "youtube" in str(action.get("uri", "")):
                        youtube_url = action["uri"]
                        break

        # اگر بازم پیدا نشد، با اسم آهنگ سرچ می‌کنیم
        if not youtube_url:
            youtube_url = f"https://www.youtube.com/results?search_query={artist}+{title}"

        log.info("Song identified: %s - %s", artist, title)
        return {
            "title": title,
            "artist": artist,
            "youtube_url": youtube_url,
            "full_title": f"{artist} - {title}",
        }

    except Exception as exc:
        log.warning("Song recognition failed: %s", exc)
        return None


async def search_and_download_song(artist: str, title: str) -> str | None:
    """
    آهنگ را با yt-dlp از یوتیوب پیدا و دانلود می‌کند.
    مسیر فایل دانلود شده را برمی‌گرداند.
    """
    import yt_dlp
    from tg_downloader_bot.utils.files import make_temp_dir

    query = f"ytsearch1:{artist} {title} official audio"
    tmp = make_temp_dir(prefix="music_")

    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(tmp / "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
    }

    try:
        loop = asyncio.get_running_loop()

        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([query])

        await loop.run_in_executor(None, _download)

        # پیدا کردن فایل دانلود شده
        files = list(tmp.glob("*.mp3"))
        if files:
            return str(files[0]), tmp
        return None, tmp

    except Exception as exc:
        log.error("Music download failed: %s", exc)
        return None, tmp
