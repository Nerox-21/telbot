"""
services/music_finder.py
========================
شناسایی آهنگ از فایل ویدیویی با استفاده از shazamio.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from shazamio import Shazam

from tg_downloader_bot.utils.logger import get_logger

log = get_logger("music_finder")


async def find_song(video_path: Path) -> dict | None:
    try:
        # اول صدا را با ffmpeg جدا می‌کنیم
        audio_path = video_path.with_suffix(".wav")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-t", "30",          # فقط ۳۰ ثانیه اول
                    "-ar", "44100",      # sample rate استاندارد
                    "-ac", "1",          # mono
                    "-f", "wav",
                    str(audio_path),
                ],
                capture_output=True,
                timeout=30,
            )
        except Exception as exc:
            log.warning("ffmpeg audio extract failed: %s", exc)
            audio_path = video_path  # اگر ffmpeg فیل کرد، مستقیم ویدیو را بده

        # حالا shazam را اجرا کن
        shazam = Shazam()
        result = await shazam.recognize(str(audio_path))

        # پاک کردن فایل موقت
        if audio_path != video_path and audio_path.exists():
            audio_path.unlink()

        if not result or "track" not in result:
            return None

        track = result["track"]
        title = track.get("title", "نامشخص")
        artist = track.get("subtitle", "نامشخص")

        log.info("Song identified: %s - %s", artist, title)
        return {
            "title": title,
            "artist": artist,
            "full_title": f"{artist} - {title}",
        }

    except Exception as exc:
        log.warning("Song recognition failed: %s", exc)
        return None


async def search_and_download_song(artist: str, title: str):
    import yt_dlp
    from tg_downloader_bot.utils.files import make_temp_dir

    query = f"ytsearch1:{artist} {title} official audio"
    tmp = make_temp_dir(prefix="music_")

    opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(tmp / "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        loop = asyncio.get_running_loop()

        def _download():
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([query])

        await asyncio.wait_for(
            loop.run_in_executor(None, _download),
            timeout=60.0
        )

        files = list(tmp.glob("*.mp3"))
        if files:
            return str(files[0]), tmp
        return None, tmp

    except asyncio.TimeoutError:
        log.error("Music download timed out")
        return None, tmp
    except Exception as exc:
        log.error("Music download failed: %s", exc)
        return None, tmp
