"""
utils/url_parser.py
===================
تشخیص و استخراج لینک از متن پیام کاربر و شناسایی پلتفرم مبدا.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse


# الگوی کلی استخراج URL.
# منطق: از http(s) شروع، تا رسیدن به فاصله/کاراکتر ممنوع ادامه پیدا می‌کند؛
# سپس هر کاراکتر انتهاییِ نقطه‌گذاری که نباید بخشی از URL باشد را trim می‌کنیم.
_URL_REGEX = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)

# نگاشت دامنه -> پلتفرم برای تشخیص خودکار.
# انکورها (?:^|\.) تضمین می‌کنند که زیررشته‌ها به‌اشتباه مچ نشوند
# (مثلاً "t.co" داخل "pinterest.com").
_PLATFORM_PATTERNS: dict[str, re.Pattern] = {
    "instagram": re.compile(r"(?:^|[/.])(instagram\.com|instagr\.am)", re.I),
    "tiktok": re.compile(r"(?:^|[/.])(tiktok\.com|(?:vm|vt)\.tiktok\.com)", re.I),
    "twitter": re.compile(r"(?:^|[/.])(twitter\.com|x\.com|t\.co)", re.I),
    "youtube": re.compile(r"(?:^|[/.])(youtube\.com|youtu\.be|youtube-nocookie\.com)", re.I),
    "pinterest": re.compile(r"(?:^|[/.])(pinterest\.com|pin\.it)", re.I),
    "facebook": re.compile(r"(?:^|[/.])(facebook\.com|fb\.watch|fb\.com)", re.I),
    "reddit": re.compile(r"(?:^|[/.])(reddit\.com|redd\.it)", re.I),
    "twitch": re.compile(r"(?:^|[/.])(twitch\.tv|clips\.twitch\.tv)", re.I),
    "vimeo": re.compile(r"(?:^|[/.])vimeo\.com", re.I),
    "dailymotion": re.compile(r"(?:^|/[/.])dailymotion\.com", re.I),
    "soundcloud": re.compile(r"(?:^|[/.])soundcloud\.com", re.I),
}


@dataclass(frozen=True)
class ParsedLink:
    """لینک استخراج‌شده همراه با پلتفرم شناسایی‌شده."""

    url: str
    platform: str  # 'instagram' | 'tiktok' | ... | 'unknown'

    def __str__(self) -> str:
        return f"[{self.platform}] {self.url}"


def detect_platform(url: str) -> str:
    """شناسایی پلتفرم یک URL. در صورت ناشناخته بودن، 'unknown' برمی‌گرداند."""
    for platform, pattern in _PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return "unknown"


def extract_links(text: str) -> list[str]:
    """استخراج تمام URLهای معتبر از متن. ترتیب را حفظ می‌کند و تکراری‌ها را حذف."""
    if not text:
        return []

    found: list[str] = []
    seen: set[str] = set()
    for match in _URL_REGEX.finditer(text):
        url = match.group(0).strip().rstrip(".,!?)")
        # trim parenthesized tail if unbalanced
        if url.endswith(")") and url.count(")") > url.count("("):
            url = url[:-1]
        # نرمال‌سازی جزئی
        if not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        found.append(url)
    return found


def parse_message_links(
    text: str, limit: int | None = None
) -> list[ParsedLink]:
    """استخراج لینک‌ها به‌همراه پلتفرم؛ با محدودیت تعداد اختیاری."""
    raw = extract_links(text)
    if limit is not None:
        raw = raw[:limit]
    return [ParsedLink(url=u, platform=detect_platform(u)) for u in raw]


def is_valid_url(url: str) -> bool:
    """اعتبارسنجی پایه یک URL."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in {"http", "https"} and parsed.netloc)
    except Exception:
        return False


def dedupe(links: Iterable[ParsedLink]) -> list[ParsedLink]:
    """حذف تکراری‌ها بر اساس URL."""
    seen: set[str] = set()
    out: list[ParsedLink] = []
    for lk in links:
        if lk.url not in seen:
            seen.add(lk.url)
            out.append(lk)
    return out
