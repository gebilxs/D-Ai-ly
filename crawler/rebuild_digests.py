#!/usr/bin/env python3
"""Rebuild digests strictly from article frontmatter dates.

Use after fixing cross-day pollution so each daily log only contains
articles whose stored `date:` matches that day.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.models import Article  # noqa: E402
from crawler.run import ARTICLES_DIR, DIGESTS_DIR, write_digest  # noqa: E402


def main() -> int:
    by_date: dict[str, list[Article]] = defaultdict(list)
    slug_by_id: dict[str, dict[str, str]] = defaultdict(dict)

    for path in sorted(ARTICLES_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta: dict[str, str] = {}
        for key in ("title", "date", "source", "source_id", "url", "summary", "article_id"):
            m = re.search(rf'^{key}:\s*["\']?(.*?)["\']?\s*$', text, re.M)
            if m:
                meta[key] = m.group(1)
        day = meta.get("date")
        if not day or not meta.get("url"):
            continue
        art = Article(
            id=meta.get("article_id") or path.stem,
            source_id=meta.get("source_id") or "unknown",
            source_name=meta.get("source") or "unknown",
            title=meta.get("title") or path.stem,
            url=meta["url"],
            published=day,
            summary=meta.get("summary") or "",
        )
        by_date[day].append(art)
        slug_by_id[day][art.id] = path.stem

    for dstr, arts in sorted(by_date.items()):
        write_digest(date.fromisoformat(dstr), arts, slug_by_id[dstr])
        print(f"digest {dstr}: {len(arts)} items")

    keep = set(by_date)
    for dpath in DIGESTS_DIR.glob("*.md"):
        day = dpath.stem
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) and day not in keep:
            dpath.unlink()
            print(f"removed empty digest {dpath.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
