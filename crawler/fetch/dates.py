from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")

_DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[-/.年](?P<m>\d{1,2})[-/.月](?P<d>\d{1,2})"),
    re.compile(r"(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})"),
]


def today_shanghai(now: Optional[datetime] = None) -> date:
    now = now or datetime.now(tz=SHANGHAI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI)
    return now.astimezone(SHANGHAI).date()


def parse_target_date(value: str) -> date:
    value = (value or "").strip().lower()
    if value in {"today", "今日", "今天"}:
        return today_shanghai()
    if value in {"yesterday", "昨日", "昨天"}:
        return today_shanghai() - timedelta(days=1)
    return date.fromisoformat(value)


def to_shanghai_date(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SHANGHAI).date()


def parse_any_datetime(text: str) -> Optional[datetime]:
    if not text:
        return None
    text = text.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=SHANGHAI)
            return dt
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        pass
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            y, mo, d = int(m.group("y")), int(m.group("m")), int(m.group("d"))
            return datetime(y, mo, d, 12, 0, tzinfo=SHANGHAI)
        except ValueError:
            continue
    if "小时前" in text or "分钟前" in text or "刚刚" in text:
        return datetime.now(tz=SHANGHAI)
    m = re.search(r"(\d+)\s*天前", text)
    if m:
        return datetime.now(tz=SHANGHAI) - timedelta(days=int(m.group(1)))
    return None


def date_from_url(url: str) -> Optional[date]:
    """Full calendar date in permalink: /2026/07/31/...

    Avoids matching量子位 `/2026/07/464328.html` where the last segment is an id.
    """
    if not url:
        return None
    m = re.search(r"/(20\d{2})/(\d{1,2})/(\d{1,2})", url)
    if not m:
        return None
    # If more digits follow, this is an article id, not a day.
    if re.match(r"\d", url[m.end() :]):
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def qbitai_url_month(url: str) -> tuple[int, int] | None:
    """量子位 permalink /YYYY/MM/<id>.html → (year, month)."""
    m = re.search(r"/(20\d{2})/(\d{1,2})/\d+(?:\.html)?", url or "")
    if not m:
        return None
    y, mo = int(m.group(1)), int(m.group(2))
    if 1 <= mo <= 12:
        return y, mo
    return None


def extract_date_near(text: str, target: date) -> Optional[date]:
    """Extract a calendar date from nearby text.

    Relative phrases (小时前/刚刚) are intentionally ignored here — they
    collapse to \"now\" and mis-bucket yesterday's posts into today.
    """
    if not text:
        return None
    if re.search(r"(小时前|分钟前|刚刚|天前)", text):
        # strip relative crumbs then look for absolute dates only
        text = re.sub(r"\d+\s*(小时前|分钟前|天前)|刚刚", " ", text)
    for pat in _DATE_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        except ValueError:
            continue
    return None
