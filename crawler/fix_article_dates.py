#!/usr/bin/env python3
"""One-shot: re-date mis-bucketed articles using RSS pubDate / URL month.

Moves qbitai posts that were stamped with the wrong calendar day (usually
because HTML relative times said \"N小时前\") into the digest for their
true Asia/Shanghai publish date.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetch.dates import parse_any_datetime, to_shanghai_date  # noqa: E402
from crawler.fetch.pipeline import load_sources  # noqa: E402
from crawler.httputil import fetch_text, looks_like_xml  # noqa: E402
from crawler.run import slugify, write_digest  # noqa: E402
from crawler.models import Article  # noqa: E402

ARTICLES = ROOT / "src" / "content" / "articles"
DIGESTS = ROOT / "src" / "content" / "digests"


def _fm(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {"_path": str(path), "_stem": path.stem}
    for key in ("title", "date", "source", "source_id", "url", "summary", "article_id"):
        m = re.search(rf'^{key}:\s*["\']?(.*?)["\']?\s*$', text, re.M)
        if m:
            out[key] = m.group(1)
    return out


def _rss_pub_map() -> dict[str, str]:
    """url -> YYYY-MM-DD (Shanghai) from live qbitai feed."""
    src = next(s for s in load_sources() if s["id"] == "qbitai")
    try:
        xml = fetch_text(src["url"], timeout=30.0)
    except Exception as e:
        print(f"rss fetch failed: {e}")
        return {}
    if not looks_like_xml(xml):
        print("rss not xml")
        return {}
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml)
    mapping: dict[str, str] = {}
    for item in root.iter():
        tag = item.tag.rsplit("}", 1)[-1]
        if tag != "item":
            continue
        link = ""
        pub_raw = ""
        for child in list(item):
            ct = child.tag.rsplit("}", 1)[-1]
            if ct == "link":
                link = "".join(child.itertext()).strip()
            if ct == "pubDate":
                pub_raw = "".join(child.itertext()).strip()
        dt = parse_any_datetime(pub_raw)
        if link and dt:
            mapping[link.rstrip("/").lower()] = to_shanghai_date(dt).isoformat()
    return mapping


def main() -> int:
    pubmap = _rss_pub_map()
    print(f"rss map size={len(pubmap)}")
    changed = 0
    by_date: dict[str, list[Article]] = defaultdict(list)
    slug_by_id: dict[str, dict[str, str]] = defaultdict(dict)

    for path in sorted(ARTICLES.glob("*.md")):
        meta = _fm(path)
        url = (meta.get("url") or "").rstrip("/").lower()
        if not url:
            continue
        old = meta.get("date")
        new = pubmap.get(url)
        if new and old and new != old:
            text = path.read_text(encoding="utf-8")
            text2 = re.sub(
                rf"^date:\s*{re.escape(old)}\s*$",
                f"date: {new}",
                text,
                count=1,
                flags=re.M,
            )
            if text2 != text:
                path.write_text(text2, encoding="utf-8")
                changed += 1
                print(f"fix {path.name}: {old} -> {new}")
            old = new
        # rebuild digests from all articles
        if not old:
            continue
        art = Article(
            id=meta.get("article_id") or path.stem,
            source_id=meta.get("source_id") or "unknown",
            source_name=meta.get("source") or "unknown",
            title=meta.get("title") or path.stem,
            url=meta.get("url") or "",
            published=old,
            summary=meta.get("summary") or "",
        )
        by_date[old].append(art)
        slug_by_id[old][art.id] = path.stem

    # Drop empty/wrong digests and rewrite
    for dpath in DIGESTS.glob("*.md"):
        if dpath.name == ".gitkeep":
            continue
        # will rewrite known dates; remove orphan later
        pass

    from datetime import date as date_cls

    for dstr, arts in sorted(by_date.items()):
        target = date_cls.fromisoformat(dstr)
        write_digest(target, arts, slug_by_id[dstr])
        print(f"digest {dstr}: {len(arts)} items")

    # Remove digests with no articles left
    keep = set(by_date)
    for dpath in DIGESTS.glob("*.md"):
        day = dpath.stem
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) and day not in keep:
            dpath.unlink()
            print(f"removed empty digest {dpath.name}")

    print(f"changed_articles={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
