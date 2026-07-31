from __future__ import annotations

import hashlib
import re
from datetime import date

from ..httputil import fetch_text
from ..models import Article
from .dates import parse_any_datetime, to_shanghai_date, today_shanghai

_TITLE_RE = re.compile(
    r"<title>([^<]+)</title>|"
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']|'
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    re.I,
)
_DATE_RE = re.compile(
    r"(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?|"
    r"20\d{2}-\d{1,2}-\d{1,2})",
)
_EMPTY_MARKERS = ("找不到", "404", "不存在", "页面不存在", "登录甲子光年")


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _clean_title(raw: str) -> str:
    t = (raw or "").strip()
    for suffix in ("｜甲子光年", "|甲子光年", "-甲子光年", "_甲子光年"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    return t


def _parse_detail(html: str) -> tuple[str | None, date | None]:
    if not html or len(html) < 200:
        return None, None
    head = html[:12000]
    title = None
    m = _TITLE_RE.search(head)
    if m:
        title = _clean_title(next(g for g in m.groups() if g))
    if not title or title in {"甲子光年|中国科技产业智库", "甲子光年"}:
        return None, None
    pub = None
    # Prefer explicit publish markers
    for pat in (
        r"发布[于时间日]*[：:\s]*((?:20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?))",
        r"((?:20\d{2}-\d{1,2}-\d{1,2}))",
    ):
        dm = re.search(pat, head)
        if not dm:
            continue
        dt = parse_any_datetime(dm.group(1))
        if dt is not None:
            pub = to_shanghai_date(dt)
            break
    return title, pub


def _probe_id(aid: int) -> tuple[str, str, date | None] | None:
    url = f"https://www.jazzyear.com/article_info.html?id={aid}"
    try:
        html = fetch_text(url, timeout=18.0)
    except Exception:
        return None
    title, pub = _parse_detail(html)
    if not title:
        return None
    return url, title, pub


def _find_high_water(start: int, floor: int = 900) -> int:
    """Coarse then fine search for a parseable recent article id."""
    hit_id = None
    for aid in range(start, floor, -5):
        if _probe_id(aid):
            hit_id = aid
            break
    if hit_id is None:
        return floor
    # Walk up a bit in case start was below tip
    cur = hit_id
    for aid in range(hit_id + 1, hit_id + 12):
        if _probe_id(aid):
            cur = aid
        else:
            break
    return cur


def fetch_jazzyear_scan(
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
    start_id: int = 1700,
    scan: int = 40,
) -> list[Article]:
    """Scan recent article_info.html?id=N pages (SPA list has no SSR links)."""
    high = _find_high_water(start_id)
    out: list[Article] = []
    seen: set[str] = set()
    older_streak = 0
    for aid in range(high + 3, max(1, high - scan), -1):
        hit = _probe_id(aid)
        if not hit:
            continue
        url, title, pub = hit
        if pub is None:
            if not date_filter:
                pub = today_shanghai()
            else:
                continue
        if date_filter and pub != target:
            if pub < target:
                older_streak += 1
                if older_streak >= 8:
                    break
            continue
        older_streak = 0
        if url in seen:
            continue
        seen.add(url)
        out.append(
            Article(
                id=_article_id(url, title),
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=url,
                published=pub.isoformat(),
                summary="",
                fetched_via="jazzyear_scan",
            )
        )
    return out
