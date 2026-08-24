from __future__ import annotations

import hashlib
import re
import urllib.error
from datetime import date, datetime, timedelta
from typing import Any

from ..httputil import fetch_json
from ..models import Article
from .dates import today_shanghai, to_shanghai_date

# m.weibo.cn container timeline for a user
_API = (
    "https://m.weibo.cn/api/container/getIndex"
    "?type=uid&value={uid}&containerid=107603{uid}"
)


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _clean_title(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"#\S+#?", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ：:，,。；; ")
    if len(text) > 48:
        for sep in ("！", "。", "？", "!", "?", "\n"):
            if sep in text[:48]:
                text = text.split(sep, 1)[0]
                break
        text = text[:48].rstrip() + "…"
    return text or "微博资讯"


def _parse_weibo_time(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    now = datetime.now().astimezone()
    if "刚刚" in raw:
        return today_shanghai()
    m = re.search(r"(\d+)\s*分钟前", raw)
    if m:
        return to_shanghai_date(now - timedelta(minutes=int(m.group(1))))
    m = re.search(r"(\d+)\s*小时前", raw)
    if m:
        return to_shanghai_date(now - timedelta(hours=int(m.group(1))))
    if raw.startswith("昨天"):
        return today_shanghai() - timedelta(days=1)
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})-(\d{1,2})", raw)
    if m:
        try:
            return date(now.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
    return None


def fetch_weibo_uid(
    uid: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool = True,
    cookie: str | None = None,
) -> list[Article]:
    url = _API.format(uid=uid)
    headers = {
        "Referer": f"https://m.weibo.cn/u/{uid}",
        "X-Requested-With": "XMLHttpRequest",
    }
    if cookie:
        headers["Cookie"] = cookie
    try:
        data: Any = fetch_json(url, timeout=25.0, headers=headers)
    except urllib.error.HTTPError as e:
        if e.code == 432:
            # m.weibo.cn anti-crawl: anonymous datacenter requests get 432.
            # A logged-in browser cookie (SUB=...) via MWEIBO_COOKIE fixes it.
            raise RuntimeError(
                f"weibo api http 432 (anti-crawl) for uid={uid}: "
                "set MWEIBO_COOKIE env/secret to a logged-in m.weibo.cn cookie"
            ) from e
        raise
    cards = ((data or {}).get("data") or {}).get("cards") or []
    out: list[Article] = []
    seen: set[str] = set()
    for card in cards:
        mblog = card.get("mblog") if isinstance(card, dict) else None
        if not isinstance(mblog, dict):
            continue
        text = mblog.get("text") or mblog.get("raw_text") or ""
        title = _clean_title(text)
        pub = _parse_weibo_time(str(mblog.get("created_at") or ""))
        if pub is None:
            continue
        if date_filter and pub != target:
            continue
        bid = str(mblog.get("bid") or mblog.get("id") or "")
        link = ""
        # Prefer explicit URL in text
        um = re.search(r"https?://t\.cn/\w+", text)
        if um:
            link = um.group(0)
        elif bid:
            link = f"https://m.weibo.cn/detail/{bid}"
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(
            Article(
                id=_article_id(link, title),
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=link,
                published=pub.isoformat(),
                summary=re.sub(r"<[^>]+>", " ", text).strip()[:400],
                fetched_via="weibo_api",
            )
        )
    if not out and (data or {}).get("ok") == 0:
        raise RuntimeError(
            f"weibo api empty for uid={uid}: {(data or {}).get('msg')}"
        )
    return out
