from __future__ import annotations

import hashlib
import re
from datetime import date
from html import unescape
from urllib.parse import urljoin, urlparse

from ..httputil import fetch_text
from ..models import Article
from .dates import date_from_url, extract_date_near, parse_any_datetime, to_shanghai_date

_SOURCE_HREF_RE: dict[str, re.Pattern[str]] = {
    "jiqizhixin": re.compile(r"/articles?/|/p/|jiqizhixin\.com/", re.I),
    "qbitai": re.compile(r"qbitai\.com/\d{4}/\d{2}", re.I),
    "geekpark": re.compile(r"/news/\d|/article/", re.I),
    "jazzyear": re.compile(r"article_info\.html\?id=\d+|article|detail|/news", re.I),
    "sina_media": re.compile(r"sina\.(cn|com)|article|t\.cn", re.I),
    "baai": re.compile(r"/view/\d+|hub\.baai|/article|/papers|/news", re.I),
}

_A_TAG_RE = re.compile(
    r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_JAZZY_ID_RE = re.compile(
    r'article_info\.html\?id=(?P<id>\d+)[^>]*>?(?P<title>[^<]{6,120})',
    re.I,
)
_JAZZY_DATE_TITLE_RE = re.compile(
    r"(?P<title>[\u4e00-\u9fffA-Za-z0-9「」『』【】（）()·、，：:\-]{8,80})"
    r".{0,40}?(?P<date>20\d{2}-\d{1,2}-\d{1,2})",
    re.S,
)


def _strip(s: str) -> str:
    s = unescape(_TAG_RE.sub(" ", s or ""))
    return _WS_RE.sub(" ", s).strip()


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _href_ok(source_id: str, href: str) -> bool:
    if not href or href.startswith(("#", "javascript:", "mailto:")):
        return False
    pat = _SOURCE_HREF_RE.get(source_id)
    if pat is None:
        return True
    return bool(pat.search(href))


def _context_window(html: str, start: int, end: int, radius: int = 320) -> str:
    a = max(0, start - radius)
    b = min(len(html), end + radius)
    return html[a:b]


def parse_list_html(
    html: str,
    *,
    base_url: str,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
) -> list[Article]:
    seen: set[str] = set()
    out: list[Article] = []

    # 甲子光年: prefer explicit article_info ids
    if source_id == "jazzyear":
        for m in _JAZZY_ID_RE.finditer(html):
            aid = m.group("id")
            title = _strip(m.group("title"))
            url = urljoin(base_url, f"article_info.html?id={aid}")
            ctx = _strip(_context_window(html, m.start(), m.end()))
            pub = extract_date_near(ctx, target)
            if pub is None:
                # search a bit further for date
                pub_dt = parse_any_datetime(ctx)
                pub = to_shanghai_date(pub_dt) if pub_dt else None
            if date_filter and pub != target:
                continue
            if not pub:
                continue
            if url in seen or len(title) < 6:
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
                    fetched_via="html",
                )
            )
        if out:
            return out

    for m in _A_TAG_RE.finditer(html):
        href = unescape(m.group(1).strip())
        title = _strip(m.group(2))
        if len(title) < 6 or len(title) > 120:
            continue
        if not _href_ok(source_id, href):
            continue
        url = urljoin(base_url, href)
        path = urlparse(url).path.rstrip("/")
        if path in {"", "/", "/index.html", "/index"}:
            continue
        if url in seen:
            continue
        ctx = _strip(_context_window(html, m.start(), m.end()))
        # Absolute dates only — never treat \"N小时前\" as today.
        pub = date_from_url(url) or extract_date_near(ctx, target)
        if date_filter and pub != target:
            continue
        if pub is None:
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
                fetched_via="html",
            )
        )
    return out


def fetch_html_list(
    url: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
    headers: dict[str, str] | None = None,
) -> list[Article]:
    text = fetch_text(url, timeout=30.0, headers=headers)
    return parse_list_html(
        text,
        base_url=url,
        source_id=source_id,
        source_name=source_name,
        target=target,
        date_filter=date_filter,
    )


def enrich_summary_from_page(url: str, max_chars: int = 400) -> str:
    try:
        html = fetch_text(url, timeout=20.0)
    except Exception:
        return ""
    for pat in (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
    ):
        m = re.search(pat, html, re.I)
        if m:
            return _strip(m.group(1))[:max_chars]
    m = re.search(r"<p[^>]*>(.*?)</p>", html, re.I | re.S)
    if m:
        return _strip(m.group(1))[:max_chars]
    return ""
