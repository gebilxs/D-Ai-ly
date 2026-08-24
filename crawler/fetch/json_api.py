from __future__ import annotations

import hashlib
from datetime import date
from typing import Any
from urllib.parse import urlencode

from ..httputil import fetch_json
from ..models import Article
from .dates import parse_any_datetime, to_shanghai_date


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _get_path(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def fetch_json_api(
    src: dict[str, Any],
    *,
    target: date,
    date_filter: bool = True,
) -> list[Article]:
    """Generic JSON list fetcher configured via sources.yaml fields."""
    sid = src["id"]
    name = src["name"]
    base_url = src["url"]
    method = (src.get("method") or "GET").upper()
    params = src.get("params") or {}
    form = src.get("form")
    # Single-page endpoints return only a handful of items; anything that
    # scrolls past between hourly runs is lost forever. `pages: N` walks
    # the page param to widen the window.
    pages = max(1, int(src.get("pages") or 1))
    items_path = src.get("items_path") or "posts"

    items: list[Any] = []
    for page in range(1, pages + 1):
        page_params = dict(params)
        if pages > 1:
            page_params["page"] = str(page)
        url = base_url
        page_form = form
        if page_params and method == "GET":
            join = "&" if "?" in url else "?"
            url = f"{url}{join}{urlencode(page_params)}"
        elif page_params and method == "POST" and page_form is None:
            # BAAI style: querystring + empty POST body
            join = "&" if "?" in url else "?"
            url = f"{url}{join}{urlencode(page_params)}"
            page_form = {}
        data = fetch_json(url, method=method, form=page_form)
        page_items = _get_path(data, items_path)
        if page_items is None and isinstance(data, list):
            page_items = data
        if not isinstance(page_items, list):
            raise RuntimeError(f"{sid}: items_path '{items_path}' not a list")
        if not page_items:
            break
        items.extend(page_items)

    title_key = src.get("title_key") or "title"
    summary_key = src.get("summary_key") or "abstract"
    date_key = src.get("date_key") or "published_at"
    link_key = src.get("link_key")
    id_key = src.get("id_key") or "id"
    url_template = src.get("url_template")

    out: list[Article] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        # Nested story_info support (BAAI)
        nested = src.get("item_nest")
        node = _get_path(it, nested) if nested else it
        if not isinstance(node, dict):
            continue
        if src.get("skip_if_true"):
            # e.g. skip events
            flag = _get_path(it, src["skip_if_true"])
            if flag:
                continue

        title = str(node.get(title_key) or "").strip()
        if not title:
            continue
        link = ""
        if link_key:
            raw_link = _get_path(it, link_key)
            if raw_link is None:
                raw_link = node.get(link_key)
            if raw_link not in (None, "", "None", "null"):
                link = str(raw_link).strip()
        if not link and url_template:
            oid = None
            if src.get("story_id_key"):
                oid = _get_path(it, src["story_id_key"])
            if oid is None:
                oid = node.get(id_key) or it.get(id_key)
            if oid is not None:
                link = url_template.format(id=oid)
        if not link:
            continue

        raw_date = node.get(date_key) or _get_path(it, date_key) or ""
        if isinstance(raw_date, (int, float)):
            # unix seconds
            from datetime import datetime, timezone

            dt = datetime.fromtimestamp(float(raw_date), tz=timezone.utc)
        else:
            # strip Chinese suffixes like 发布/分享
            text = str(raw_date).replace("发布", "").replace("分享", "").strip()
            dt = parse_any_datetime(text)
        if dt is None:
            continue
        pub = to_shanghai_date(dt)
        if date_filter and pub != target:
            continue
        summary = str(node.get(summary_key) or "").strip()
        out.append(
            Article(
                id=_article_id(link, title),
                source_id=sid,
                source_name=name,
                title=title,
                url=link,
                published=pub.isoformat(),
                summary=summary[:800],
                fetched_via="json_api",
            )
        )
    return out
