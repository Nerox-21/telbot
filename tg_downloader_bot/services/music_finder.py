"""
services/music_finder.py
========================
شناسایی آهنگ از فایل ویدیویی با استفاده از AudD API.
"""
from __future__ import annotations

import asyncio
import subprocess
import aiohttp
from pathlib import Path

from tg_downloader_bot.utils.logger import get_logger

log = get_logger("music_finder")

AUDD_API_TOKEN = "06552c7300801346f22e53984852107e"


async def find_song(video_path: Path) -> dict | None:
    try:
        # استخراج صدا با ffmpeg
        audio_path = video_path.with_suffix(".mp3")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(video_path),
                    "-t", "30",
                    "-ar", "44100",
                    "-ac", "1",
                    "-f", "mp3",
                    str(audio_path),
                ],
                capture_output=True,
                timeout=30,
            )
        except Exception as exc:
            log.warning("ffmpeg extract failed: %s", exc)
            audio_path = video_path

        # ارسال به AudD
        async with aiohttp.ClientSession() as session:
            with open(audio_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("api_token", AUDD_API_TOKEN)
                data.add_field("return", "apple_music,spotify")
                data.add_field("file", f, filename="audio.mp3", content_type="audio/mpeg")

                async with session.post(
                    "https://api.audd.io/",
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    result = await resp.json()

        # پاک کردن فایل موقت
        if audio_path != video_path and audio_path.exists():
            audio_path.unlink()

        if not result or result.get("status") != "success" or not result.get("result"):
            log.warning("AudD returned no result: %s", result)
            return None

        track = result["result"]
        title = track.get("title", "نامشخص")
        artist = track.get("artist", "نامشخص")

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
    from tg_downloader_bot.utils.files import make_temp_dir

    tmp = make_temp_dir(prefix="music_")

    try:
        loop = asyncio.get_running_loop()

        def _download():
            subprocess.run(
                [
                    "spotdl",
                    f"{artist} {title}",
                    "--output", str(tmp),
                    "--format", "mp3",
                    "--bitrate", "192k",
                ],
                capture_output=True,
                timeout=60,
            )

        await asyncio.wait_for(
            loop.run_in_executor(None, _download),
            timeout=70.0
        )

        files = list(tmp.glob("*.mp3"))
        if files:
            return str(files[0]), tmp

        # اگر spotdl فیل کرد، SoundCloud امتحان کن
        log.warning("spotdl failed, trying SoundCloud...")
        return await _download_from_soundcloud(artist, title, tmp)

    except Exception as exc:
        log.error("spotdl failed: %s", exc)
        return await _download_from_soundcloud(artist, title, tmp)


async def _download_from_soundcloud(artist: str, title: str, tmp: Path):
    import yt_dlp

    query = f"scsearch1:{artist} {title}"

    opts = {
        "format": "bestaudio/best",
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

    except Exception as exc:
        log.error("SoundCloud download failed: %s", exc)
        return None, tmp
