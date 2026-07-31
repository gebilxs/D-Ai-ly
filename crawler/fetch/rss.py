from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import date
from xml.etree.ElementTree import Element

from ..httputil import fetch_text
from ..models import Article
from .dates import parse_any_datetime, to_shanghai_date


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _text(el: Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()


def _find_child(parent: Element, names: set[str]) -> Element | None:
    for child in list(parent):
        if _local(child.tag) in names:
            return child
    return None


def _article_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).strip().encode("utf-8")).hexdigest()[:16]


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse_feed_xml(
    xml_text: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
) -> list[Article]:
    root = ET.fromstring(xml_text)
    root_local = _local(root.tag)
    articles: list[Article] = []

    if root_local == "feed":
        entries = [c for c in root if _local(c.tag) == "entry"]
        for entry in entries:
            title = _text(_find_child(entry, {"title"}))
            link = ""
            for child in entry:
                if _local(child.tag) == "link":
                    href = child.attrib.get("href") or ""
                    rel = child.attrib.get("rel", "alternate")
                    if href and rel in ("alternate", ""):
                        link = href
                        break
            if not link:
                for child in entry:
                    if _local(child.tag) == "link" and child.attrib.get("href"):
                        link = child.attrib["href"]
                        break
            published_raw = _text(
                _find_child(entry, {"published", "updated", "issued"})
            )
            summary = _strip_html(
                _text(_find_child(entry, {"summary", "content"}))
            )
            art = _maybe_article(
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=link,
                published_raw=published_raw,
                summary=summary,
                target=target,
                via="rss",
            )
            if art:
                articles.append(art)
        return articles

    channel = root if root_local == "channel" else _find_child(root, {"channel"}) or root
    items = [c for c in channel if _local(c.tag) == "item"]
    if not items:
        items = [c for c in root.iter() if _local(c.tag) == "item"]
    for item in items:
        title = _text(_find_child(item, {"title"}))
        link = _text(_find_child(item, {"link"}))
        if not link:
            guid = _find_child(item, {"guid"})
            if guid is not None and (
                guid.attrib.get("isPermaLink", "true").lower() != "false"
            ):
                link = _text(guid)
        published_raw = _text(
            _find_child(item, {"pubDate", "date", "published", "updated"})
        )
        if not published_raw:
            for child in item:
                if _local(child.tag) == "date":
                    published_raw = _text(child)
                    break
        summary = _strip_html(
            _text(_find_child(item, {"description", "summary", "encoded", "content"}))
        )
        art = _maybe_article(
            source_id=source_id,
            source_name=source_name,
            title=title,
            url=link,
            published_raw=published_raw,
            summary=summary,
            target=target,
            via="rss",
        )
        if art:
            articles.append(art)
    return articles


def _maybe_article(
    *,
    source_id: str,
    source_name: str,
    title: str,
    url: str,
    published_raw: str,
    summary: str,
    target: date,
    via: str,
) -> Article | None:
    title = (title or "").strip()
    url = (url or "").strip()
    if not title or not url:
        return None
    dt = parse_any_datetime(published_raw)
    if dt is None:
        return None
    if to_shanghai_date(dt) != target:
        return None
    return Article(
        id=_article_id(url, title),
        source_id=source_id,
        source_name=source_name,
        title=title,
        url=url,
        published=target.isoformat(),
        summary=summary[:800],
        fetched_via=via,
    )


def fetch_rss(
    url: str,
    *,
    source_id: str,
    source_name: str,
    target: date,
) -> list[Article]:
    text = fetch_text(url, timeout=30.0)
    return parse_feed_xml(
        text, source_id=source_id, source_name=source_name, target=target
    )
