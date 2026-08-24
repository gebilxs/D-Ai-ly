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

# Article byline footer: <span class="author name">编辑：甲子光年</span>
# <span class="time">2026-07-20</span>. Related-article lists use
# class="time font-12", so the exact-class match only ever picks this
# article's own publish date.
_BYLINE_TIME_RE = re.compile(
    r'class="author[^"]*"[^>]*>[^<]*</span>\s*<span class="time">'
    r"(20\d{2}-\d{1,2}-\d{1,2})</span>"
)

_PUBLISH_MARK_RE = re.compile(r"发布[于时间日]*[：:\s]*(20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}日?)")


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
    # The publish date sits in the byline footer deep in the document
    # (past the old 12k head window). Search the whole page, anchored on
    # the byline so related-article dates can never be picked up instead.
    for pat in (_BYLINE_TIME_RE, _PUBLISH_MARK_RE):
        dm = pat.search(html)
        if not dm:
            continue
        dt = parse_any_datetime(dm.group(1))
        if dt is not None:
            pub = to_shanghai_date(dt)
            break
    return title, pub


ProbeResult = tuple[str, str, date | None] | None


def _probe_id(aid: int, cache: dict[int, ProbeResult] | None = None) -> ProbeResult:
    if cache is not None and aid in cache:
        return cache[aid]
    url = f"https://www.jazzyear.com/article_info.html?id={aid}"
    try:
        html = fetch_text(url, timeout=18.0)
    except Exception:
        result: ProbeResult = None
    else:
        result = None
        title, pub = _parse_detail(html)
        if title:
            result = (url, title, pub)
    if cache is not None:
        cache[aid] = result
    return result


def _find_high_water(
    start: int,
    floor: int = 900,
    *,
    cache: dict[int, ProbeResult] | None = None,
    max_gap: int = 8,
) -> int:
    """Locate the newest parseable article id.

    Article ids grow over time and contain gaps, so the configured
    ``start`` drifts below the tip. Coarse-scan down from ``start`` for a
    base hit, then stride up in steps of 10 and single-step backfill,
    tolerating ``max_gap`` consecutive misses.
    """
    hit_id = None
    for aid in range(start, floor, -5):
        if _probe_id(aid, cache):
            hit_id = aid
            break
    if hit_id is None:
        return floor
    cur = hit_id
    while True:
        nxt = cur + 10
        if _probe_id(nxt, cache):
            cur = nxt
            continue
        tip = cur
        misses = 0
        probe = cur
        while misses <= max_gap:
            probe += 1
            if _probe_id(probe, cache):
                tip = probe
                misses = 0
            else:
                misses += 1
        return tip


def fetch_jazzyear_scan(
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
    start_id: int = 1700,
    scan: int = 40,
) -> list[Article]:
    """Scan recent article_info.html?id=N pages (SPA list has no SSR links).

    Article ids are NOT strictly date-ordered, so the whole window is
    date-filtered instead of early-stopping on older dates.
    """
    cache: dict[int, ProbeResult] = {}
    high = _find_high_water(start_id, cache=cache)
    out: list[Article] = []
    seen: set[str] = set()
    for aid in range(high, max(1, high - scan), -1):
        hit = _probe_id(aid, cache)
        if not hit:
            continue
        url, title, pub = hit
        if pub is None:
            if not date_filter:
                pub = today_shanghai()
            else:
                continue
        if date_filter and pub != target:
            continue
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
