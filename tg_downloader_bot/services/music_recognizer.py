"""
services/music_recognizer.py
=============================
تشخیص آهنگ از فایل ویدیو/صوتی با استفاده از ShazamIO.
ShazamIO رایگان است و نیاز به API key ندارد.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from tg_downloader_bot.utils.logger import get_logger

log = get_logger("music_recognizer")


class MusicRecognitionResult:
    def __init__(self):
        self.found: bool = False
        self.title: str = ""
        self.artist: str = ""
        self.album: str = ""
        self.year: str = ""
        self.cover_url: str = ""
        self.youtube_url: str = ""
        self.apple_music_url: str = ""

    def format_message(self) -> str:
        if not self.found:
            return "🎵 آهنگی تشخیص داده نشد."

        lines = [f"🎵 <b>{self.title}</b>"]
        if self.artist:
            lines.append(f"👤 {self.artist}")
        if self.album:
            lines.append(f"💿 {self.album}")
        if self.year:
            lines.append(f"📅 {self.year}")
        if self.youtube_url:
            lines.append(f"\n🔗 <a href='{self.youtube_url}'>گوش بده در YouTube</a>")
        if self.apple_music_url:
            lines.append(f"🍎 <a href='{self.apple_music_url}'>Apple Music</a>")

        return "\n".join(lines)


def _extract_audio(video_path: Path, audio_path: Path) -> bool:
    """استخراج صدا از ویدیو با ffmpeg (فقط ۳۰ ثانیه اول)"""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-t", "30",          # فقط ۳۰ ثانیه
                "-ar", "44100",
                "-ac", "1",
                "-f", "mp3",
                str(audio_path),
            ],
            capture_output=True,
            timeout=60,
        )
        return result.returncode == 0 and audio_path.exists()
    except Exception as e:
        log.error("ffmpeg audio extract error: %s", e)
        return False


async def recognize_from_file(file_path: Path) -> MusicRecognitionResult:
    """تشخیص آهنگ از یک فایل ویدیو یا صوتی"""
    result = MusicRecognitionResult()

    try:
        from shazamio import Shazam
    except ImportError:
        log.error("shazamio not installed")
        return result

    # اگر ویدیو بود، اول صدا رو استخراج کن
    audio_path = file_path
    temp_audio = None

    video_exts = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"}
    if file_path.suffix.lower() in video_exts:
        temp_audio = file_path.parent / f"{file_path.stem}_audio.mp3"
        log.info("Extracting audio from video: %s", file_path.name)
        if _extract_audio(file_path, temp_audio):
            audio_path = temp_audio
        else:
            log.warning("Audio extraction failed, trying with original file")

    try:
        shazam = Shazam()
        log.info("Recognizing music from: %s", audio_path.name)
        out = await shazam.recognize(str(audio_path))

        if not out or "matches" not in out or not out["matches"]:
            log.info("No music match found")
            return result

        track = out.get("track", {})
        if not track:
            return result

        result.found = True
        result.title = track.get("title", "")
        result.artist = track.get("subtitle", "")

        # متادیتا اضافه
        sections = track.get("sections", [])
        for section in sections:
            if section.get("type") == "SONG":
                for meta in section.get("metadata", []):
                    if meta.get("title") == "Album":
                        result.album = meta.get("text", "")
                    elif meta.get("title") == "Released":
                        result.year = meta.get("text", "")

        # کاور آهنگ
        images = track.get("images", {})
        result.cover_url = images.get("coverarthq") or images.get("coverart", "")

        # لینک‌های خارجی
        hub = track.get("hub", {})
        for action in hub.get("actions", []):
            uri = action.get("uri", "")
            if "youtube" in uri or "youtu.be" in uri:
                result.youtube_url = uri

        for provider in hub.get("providers", []):
            for action in provider.get("actions", []):
                uri = action.get("uri", "")
                if "apple" in uri or "music.apple" in uri:
                    result.apple_music_url = uri

        # اگر یوتیوب پیدا نشد، لینک جستجو بساز
        if not result.youtube_url and result.title:
            query = f"{result.artist} {result.title}".strip().replace(" ", "+")
            result.youtube_url = f"https://www.youtube.com/results?search_query={query}"

        log.info("Recognized: %s - %s", result.artist, result.title)

    except Exception as e:
        log.error("Shazam recognition error: %s", e)
    finally:
        # پاک کردن فایل صوتی موقت
        if temp_audio and temp_audio.exists():
            try:
                temp_audio.unlink()
            except Exception:
                pass

    return result
