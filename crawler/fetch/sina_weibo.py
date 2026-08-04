from __future__ import annotations

import hashlib
import re
from datetime import date

from ..httputil import fetch_text
from ..models import Article
from .dates import parse_any_datetime, to_shanghai_date, today_shanghai

# Blocks like: 新智元2026-07-31 21:28来自 ... text http://t.cn/xxx
_BLOCK_RE = re.compile(
    r"(?P<title_host>新智元|机器之心|量子位)?"
    r"(?P<date>20\d{2}-\d{1,2}-\d{1,2})\s+\d{1,2}:\d{2}"
    r"(?:来自[^\n]{0,40})?"
    r"(?P<body>.{20,800}?)"
    r"(?P<url>https?://t\.cn/\w+|https?://[\w./\-_%]+sina[\w./\-_%]*)",
    re.S,
)

_FALLBACK_RE = re.compile(
    r"(?P<date>20\d{2}-\d{1,2}-\d{1,2})\s+\d{1,2}:\d{2}"
    r".{0,60}?"
    r"(?P<body>.{15,500}?)"
    r"(?P<url>https?://t\.cn/\w+)",
    re.S,
)

# Relative crumbs must sit on the same short block as the t.cn link.
# Do NOT use re.S here — otherwise "今天/小时前" from a new post can
# latch onto an older post's short URL further down the page.
_RELATIVE_RE = re.compile(
    r"(?:今天|小时前|分钟前|刚刚).{0,80}?(?P<body>.{15,200}?)(?P<url>https?://t\.cn/\w+)",
)


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _norm_url(url: str) -> str:
    return (url or "").strip().rstrip("/").lower()


def _clean_title(body: str) -> str:
    body = re.sub(r"\s+", " ", body).strip()
    body = re.sub(r"#\S+", "", body)
    body = body.strip(" ：:，,。；; ")
    if len(body) > 48:
        # first sentence-ish
        for sep in ("！", "。", "？", "!", "?", "\n"):
            if sep in body[:48]:
                body = body.split(sep, 1)[0]
                break
        body = body[:48].rstrip() + "…"
    return body or "微博资讯"


def parse_sina_weibo_text(
    text: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
) -> list[Article]:
    """Parse plain-text (tags already stripped) sina media timeline."""
    seen: set[str] = set()
    out: list[Article] = []

    for pat in (_BLOCK_RE, _FALLBACK_RE):
        for m in pat.finditer(text):
            dt = parse_any_datetime(m.group("date"))
            if dt is None:
                continue
            pub = to_shanghai_date(dt)
            link = m.group("url").strip()
            key = _norm_url(link)
            if not key or key in seen:
                continue
            # Skip homepage noise
            if "sina.cn/media" in link and "t.cn" not in link:
                continue
            # Always reserve the URL once an absolute date is known —
            # even when it is not today's target. Otherwise the relative
            # "今天/小时前" pass can re-stamp yesterday's short links as today.
            seen.add(key)
            if date_filter and pub != target:
                continue
            title = _clean_title(m.group("body"))
            out.append(
                Article(
                    id=_article_id(link, title),
                    source_id=source_id,
                    source_name=source_name,
                    title=title,
                    url=link,
                    published=pub.isoformat(),
                    summary=re.sub(r"\s+", " ", m.group("body")).strip()[:400],
                    fetched_via="sina_weibo",
                )
            )

    # Relative "今天" posts without absolute date: treat as today when present
    if not date_filter or target == today_shanghai():
        for m in _RELATIVE_RE.finditer(text):
            link = m.group("url").strip()
            key = _norm_url(link)
            if not key or key in seen:
                continue
            title = _clean_title(m.group("body"))
            seen.add(key)
            out.append(
                Article(
                    id=_article_id(link, title),
                    source_id=source_id,
                    source_name=source_name,
                    title=title,
                    url=link,
                    published=today_shanghai().isoformat(),
                    summary=re.sub(r"\s+", " ", m.group("body")).strip()[:400],
                    fetched_via="sina_weibo",
                )
            )
    return out


def fetch_sina_weibo_media(
    url: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
) -> list[Article]:
    html = fetch_text(url, timeout=30.0)
    # Prefer visible text extraction over raw tags
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    return parse_sina_weibo_text(
        text,
        source_id=source_id,
        source_name=source_name,
        target=target,
        date_filter=date_filter,
    )
