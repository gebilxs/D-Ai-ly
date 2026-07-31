from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..httputil import fetch_text, looks_like_xml
from ..models import Article
from .html import enrich_summary_from_page, fetch_html_list
from .jazzyear import fetch_jazzyear_scan
from .json_api import fetch_json_api
from .rss import parse_feed_xml
from .sina_weibo import fetch_sina_weibo_media
from .weibo_api import fetch_weibo_uid

ROOT = Path(__file__).resolve().parents[1]
SOURCES_YAML = ROOT / "sources.yaml"


def load_sources(path: Path | None = None) -> list[dict[str, Any]]:
    data = yaml.safe_load((path or SOURCES_YAML).read_text(encoding="utf-8"))
    return list(data.get("sources") or [])


def _dedupe(articles: list[Article]) -> list[Article]:
    by_url: dict[str, Article] = {}
    by_title: dict[str, Article] = {}
    ordered: list[Article] = []
    for art in articles:
        key_url = art.url.rstrip("/").lower()
        key_title = art.title.strip().lower()
        if key_url in by_url:
            continue
        if key_title and key_title in by_title:
            continue
        by_url[key_url] = art
        if key_title:
            by_title[key_title] = art
        ordered.append(art)
    return ordered


def _try_rss_urls(
    urls: list[str],
    *,
    source_id: str,
    source_name: str,
    target: date,
    date_filter: bool,
) -> tuple[list[Article], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    for url in urls:
        if not url:
            continue
        try:
            text = fetch_text(url, timeout=30.0)
            if not looks_like_xml(text):
                errors.append(
                    {
                        "source_id": source_id,
                        "stage": "rss",
                        "url": url,
                        "error": "response is not XML/RSS (possible login wall)",
                    }
                )
                continue
            if date_filter:
                arts = parse_feed_xml(
                    text,
                    source_id=source_id,
                    source_name=source_name,
                    target=target,
                )
            else:
                arts = _parse_rss_all(
                    text, source_id=source_id, source_name=source_name
                )
            if arts:
                return arts, errors
            errors.append(
                {
                    "source_id": source_id,
                    "stage": "rss",
                    "url": url,
                    "error": "parsed 0 items for target filter",
                }
            )
        except Exception as e:
            errors.append(
                {
                    "source_id": source_id,
                    "stage": "rss",
                    "url": url,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
    return [], errors


def _parse_rss_all(xml_text: str, *, source_id: str, source_name: str) -> list[Article]:
    """Parse RSS/Atom without day filter (for health checks)."""
    from datetime import date as date_cls
    from .rss import parse_feed_xml
    from .dates import parse_any_datetime, to_shanghai_date
    import xml.etree.ElementTree as ET
    import hashlib
    import re
    from xml.etree.ElementTree import Element

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    def text(el: Element | None) -> str:
        if el is None:
            return ""
        return "".join(el.itertext()).strip()

    def find_child(parent: Element, names: set[str]) -> Element | None:
        for child in list(parent):
            if local(child.tag) in names:
                return child
        return None

    def strip_html(s: str) -> str:
        s = re.sub(r"<[^>]+>", " ", s or "")
        return re.sub(r"\s+", " ", s).strip()

    root = ET.fromstring(xml_text)
    articles: list[Article] = []
    root_local = local(root.tag)
    entries = []
    if root_local == "feed":
        entries = [c for c in root if local(c.tag) == "entry"]
        for entry in entries:
            title = text(find_child(entry, {"title"}))
            link = ""
            for child in entry:
                if local(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
            published_raw = text(find_child(entry, {"published", "updated", "issued"}))
            summary = strip_html(text(find_child(entry, {"summary", "content"})))
            dt = parse_any_datetime(published_raw)
            if not title or not link or dt is None:
                continue
            pub = to_shanghai_date(dt)
            articles.append(
                Article(
                    id=hashlib.sha1(link.encode()).hexdigest()[:16],
                    source_id=source_id,
                    source_name=source_name,
                    title=title,
                    url=link,
                    published=pub.isoformat(),
                    summary=summary[:800],
                    fetched_via="rss",
                )
            )
        return articles

    channel = root if root_local == "channel" else find_child(root, {"channel"}) or root
    items = [c for c in channel if local(c.tag) == "item"] or [
        c for c in root.iter() if local(c.tag) == "item"
    ]
    for item in items:
        title = text(find_child(item, {"title"}))
        link = text(find_child(item, {"link"}))
        published_raw = text(
            find_child(item, {"pubDate", "date", "published", "updated"})
        )
        summary = strip_html(
            text(find_child(item, {"description", "summary", "encoded", "content"}))
        )
        dt = parse_any_datetime(published_raw)
        if not title or not link or dt is None:
            continue
        pub = to_shanghai_date(dt)
        articles.append(
            Article(
                id=hashlib.sha1(link.encode()).hexdigest()[:16],
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=link,
                published=pub.isoformat(),
                summary=summary[:800],
                fetched_via="rss",
            )
        )
    return articles


def fetch_source(
    src: dict[str, Any],
    target: date,
    *,
    date_filter: bool = True,
) -> tuple[list[Article], list[dict[str, Any]]]:
    sid = src["id"]
    name = src["name"]
    kind = src.get("kind", "html")
    errors: list[dict[str, Any]] = []
    arts: list[Article] = []

    try:
        if kind == "rss":
            urls = [src.get("url") or ""]
            urls.extend(src.get("mirrors") or [])
            arts, errors = _try_rss_urls(
                urls,
                source_id=sid,
                source_name=name,
                target=target,
                date_filter=date_filter,
            )
            if not arts:
                fallback = src.get("html_fallback")
                if fallback:
                    try:
                        arts = fetch_html_list(
                            fallback,
                            source_id=sid,
                            source_name=name,
                            target=target,
                            date_filter=date_filter,
                        )
                    except Exception as e2:
                        errors.append(
                            {
                                "source_id": sid,
                                "stage": "html_fallback",
                                "url": fallback,
                                "error": f"{type(e2).__name__}: {e2}",
                            }
                        )
            return arts, errors

        if kind == "json_api":
            arts = fetch_json_api(src, target=target, date_filter=date_filter)
            return arts, errors

        if kind == "sina_weibo":
            url = src.get("url") or ""
            arts = fetch_sina_weibo_media(
                url,
                source_id=sid,
                source_name=name,
                target=target,
                date_filter=date_filter,
            )
            return arts, errors

        if kind == "weibo_api":
            uid = str(src.get("uid") or "")
            if not uid:
                raise RuntimeError(f"{sid}: weibo_api requires uid")
            arts = fetch_weibo_uid(
                uid,
                source_id=sid,
                source_name=name,
                target=target,
                date_filter=date_filter,
            )
            return arts, errors

        if kind == "jazzyear_scan":
            arts = fetch_jazzyear_scan(
                source_id=sid,
                source_name=name,
                target=target,
                date_filter=date_filter,
                start_id=int(src.get("start_id") or 1700),
                scan=int(src.get("scan") or 40),
            )
            return arts, errors

        # html primary
        url = src.get("url") or ""
        arts = fetch_html_list(
            url,
            source_id=sid,
            source_name=name,
            target=target,
            date_filter=date_filter,
        )
        return arts, errors
    except Exception as e:
        errors.append(
            {
                "source_id": sid,
                "stage": kind,
                "url": src.get("url"),
                "error": f"{type(e).__name__}: {e}",
            }
        )
        return [], errors


def fetch_all(
    target: date,
    *,
    sources_path: Path | None = None,
    enrich: bool = True,
    date_filter: bool = True,
) -> tuple[list[Article], list[dict[str, Any]]]:
    sources = load_sources(sources_path)
    all_arts: list[Article] = []
    all_errors: list[dict[str, Any]] = []
    for src in sources:
        if src.get("enabled") is False:
            all_errors.append(
                {
                    "source_id": src.get("id"),
                    "stage": "disabled",
                    "url": src.get("url"),
                    "error": src.get("disabled_reason") or "source disabled",
                }
            )
            continue
        arts, errs = fetch_source(src, target, date_filter=date_filter)
        all_arts.extend(arts)
        all_errors.extend(errs)
    deduped = _dedupe(all_arts)
    if enrich:
        for art in deduped:
            if not art.summary:
                art.summary = enrich_summary_from_page(art.url)
    return deduped, all_errors
