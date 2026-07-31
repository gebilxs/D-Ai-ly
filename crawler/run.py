#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRAWLER_DIR = Path(__file__).resolve().parent

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(ROOT))

from crawler.fetch.dates import parse_target_date  # noqa: E402
from crawler.fetch.pipeline import fetch_all  # noqa: E402
from crawler.models import Article  # noqa: E402

ARTICLES_DIR = ROOT / "src" / "content" / "articles"
DIGESTS_DIR = ROOT / "src" / "content" / "digests"
FIXTURE_PATH = CRAWLER_DIR / "fixtures" / "demo_articles.jsonl"
ERRORS_PATH = CRAWLER_DIR / "last_errors.json"

SOURCE_ORDER = [
    "jiqizhixin",
    "qbitai",
    "geekpark",
    "jazzyear",
    "sina_media",
    "baai",
]


def slugify(title: str, fallback: str) -> str:
    s = re.sub(r"\s+", "-", (title or "").strip().lower())
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff\-]+", "", s)
    s = s.strip("-")[:48]
    return s or fallback


def yaml_escape(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def load_existing_keys() -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    titles: set[str] = set()
    if not ARTICLES_DIR.exists():
        return urls, titles
    for path in ARTICLES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        um = re.search(r'^url:\s*["\']?(.+?)["\']?\s*$', text, re.M)
        tm = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.M)
        if um:
            urls.add(um.group(1).strip().rstrip("/").lower())
        if tm:
            titles.add(tm.group(1).strip().lower())
    return urls, titles


def write_article(art: Article) -> Path:
    slug = slugify(art.title, art.id)
    path = ARTICLES_DIR / f"{slug}.md"
    if path.exists():
        # collision: append short id
        path = ARTICLES_DIR / f"{slug}-{art.id[:8]}.md"
    summary = (art.summary or "").replace("\n", " ").strip()
    fm = "\n".join(
        [
            "---",
            f"title: {yaml_escape(art.title)}",
            f"date: {art.published}",
            f"source: {yaml_escape(art.source_name)}",
            f"source_id: {art.source_id}",
            f"url: {yaml_escape(art.url)}",
            f"summary: {yaml_escape(summary)}",
            "tags:",
            "  - AI",
            f"article_id: {art.id}",
            "---",
            "",
            "本页为资讯索引，完整报道请阅读原文。",
            "",
        ]
    )
    path.write_text(fm, encoding="utf-8")
    return path


def write_digest(target: date, articles: list[Article], new_slugs: dict[str, str]) -> Path:
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGESTS_DIR / f"{target.isoformat()}.md"
    by_source: dict[str, list[Article]] = defaultdict(list)
    for a in articles:
        by_source[a.source_id].append(a)

    ordered_ids = [s for s in SOURCE_ORDER if s in by_source]
    ordered_ids.extend(sorted(k for k in by_source if k not in SOURCE_ORDER))

    item_lines: list[str] = ["items:"]
    for a in articles:
        slug = new_slugs.get(a.id) or slugify(a.title, a.id)
        excerpt = (a.summary or "").replace("\n", " ").strip()
        if len(excerpt) > 160:
            excerpt = excerpt[:157] + "…"
        item_lines.extend(
            [
                f"  - title: {yaml_escape(a.title)}",
                f"    slug: {slug}",
                f"    source: {yaml_escape(a.source_name)}",
                f"    source_id: {a.source_id}",
                f"    url: {yaml_escape(a.url)}",
                f"    summary: {yaml_escape(excerpt)}",
            ]
        )

    lines = [
        "---",
        f'title: "今日 AI 速报 · {target.isoformat()}"',
        f"date: {target.isoformat()}",
        f"count: {len(articles)}",
        *item_lines,
        "---",
        "",
        f"今天共收录 **{len(articles)}** 条科技资讯，按来源整理如下。",
        "",
    ]

    for sid in ordered_ids:
        items = by_source[sid]
        name = items[0].source_name
        lines.append(f"## {name}")
        lines.append("")
        for a in items:
            excerpt = (a.summary or "").strip()
            if len(excerpt) > 120:
                excerpt = excerpt[:117] + "…"
            lines.append(f"- **{a.title}**")
            if excerpt:
                lines.append(f"  - {excerpt}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def load_fixture(target: date) -> list[Article]:
    if not FIXTURE_PATH.exists():
        return []
    arts: list[Article] = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        arts.append(
            Article(
                id=d.get("id") or slugify(d.get("title", ""), "item"),
                source_id=d.get("source_id", "fixture"),
                source_name=d.get("source_name", "fixture"),
                title=d["title"],
                url=d["url"],
                published=target.isoformat(),
                summary=d.get("summary", ""),
                fetched_via="fixture",
            )
        )
    return arts


def map_fixture_sources(arts: list[Article]) -> list[Article]:
    """Map demo fixture source names onto real source ids when needed."""
    name_to_id = {
        "机器之心": "jiqizhixin",
        "量子位": "qbitai",
        "极客公园": "geekpark",
        "甲子光年": "jazzyear",
        "新浪媒体号": "sina_media",
        "智源社区": "baai",
        "DeepSeek": "jiqizhixin",
    }
    out = []
    for a in arts:
        sid = a.source_id
        if sid == "fixture":
            sid = name_to_id.get(a.source_name, "jiqizhixin")
        out.append(
            Article(
                id=a.id,
                source_id=sid,
                source_name=a.source_name,
                title=a.title,
                url=a.url,
                published=a.published,
                summary=a.summary,
                fetched_via=a.fetched_via,
            )
        )
    return out


def run(
    date_str: str = "today",
    *,
    allow_fixture: bool = True,
    force_fixture: bool = False,
) -> dict:
    target = parse_target_date(date_str)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)

    errors: list[dict] = []
    if force_fixture:
        articles = map_fixture_sources(load_fixture(target))
        errors.append(
            {
                "source_id": "_fixture",
                "stage": "forced",
                "error": "loaded demo fixtures via --fixture",
            }
        )
    else:
        articles, errors = fetch_all(target)
        if not articles and allow_fixture:
            fixtures = map_fixture_sources(load_fixture(target))
            if fixtures:
                articles = fixtures
                errors.append(
                    {
                        "source_id": "_fixture",
                        "stage": "fallback",
                        "error": "all sources empty/unreachable; loaded demo fixtures",
                    }
                )

    existing_urls, existing_titles = load_existing_keys()
    created: list[str] = []
    day_articles: list[Article] = []
    slug_by_id: dict[str, str] = {}

    # Include already-written articles for this date into digest
    for path in ARTICLES_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        dm = re.search(r"^date:\s*(\d{4}-\d{2}-\d{2})", text, re.M)
        if not dm or dm.group(1) != target.isoformat():
            continue
        tm = re.search(r'^title:\s*["\']?(.*?)["\']?\s*$', text, re.M)
        sm = re.search(r'^source:\s*["\']?(.*?)["\']?\s*$', text, re.M)
        sidm = re.search(r"^source_id:\s*(\S+)", text, re.M)
        um = re.search(r'^url:\s*["\']?(.*?)["\']?\s*$', text, re.M)
        sum_m = re.search(r'^summary:\s*["\']?(.*?)["\']?\s*$', text, re.M)
        idm = re.search(r"^article_id:\s*(\S+)", text, re.M)
        if not (tm and um):
            continue
        aid = idm.group(1) if idm else path.stem
        art = Article(
            id=aid,
            source_id=sidm.group(1) if sidm else "unknown",
            source_name=sm.group(1) if sm else "unknown",
            title=tm.group(1),
            url=um.group(1),
            published=target.isoformat(),
            summary=sum_m.group(1) if sum_m else "",
        )
        day_articles.append(art)
        slug_by_id[aid] = path.stem

    for art in articles:
        key_url = art.url.rstrip("/").lower()
        key_title = art.title.strip().lower()
        if key_url in existing_urls or (key_title and key_title in existing_titles):
            # still ensure it's in day's digest list
            if not any(a.url.rstrip("/").lower() == key_url for a in day_articles):
                day_articles.append(art)
                slug_by_id[art.id] = slugify(art.title, art.id)
            continue
        path = write_article(art)
        created.append(str(path.relative_to(ROOT)))
        existing_urls.add(key_url)
        if key_title:
            existing_titles.add(key_title)
        day_articles.append(art)
        slug_by_id[art.id] = path.stem

    # Dedupe day_articles by url
    seen: set[str] = set()
    unique_day: list[Article] = []
    for a in day_articles:
        k = a.url.rstrip("/").lower()
        if k in seen:
            continue
        seen.add(k)
        unique_day.append(a)

    digest_path = write_digest(target, unique_day, slug_by_id)
    ERRORS_PATH.write_text(
        json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    result = {
        "date": target.isoformat(),
        "fetched": len(articles),
        "created": len(created),
        "digest_count": len(unique_day),
        "digest": str(digest_path.relative_to(ROOT)),
        "errors": len(errors),
        "new_files": created,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="D-Ai-ly crawler → Markdown content")
    p.add_argument("--date", default="today", help="today or YYYY-MM-DD")
    p.add_argument(
        "--fixture",
        action="store_true",
        help="force load demo fixtures (skip live crawl)",
    )
    p.add_argument(
        "--no-fixture",
        action="store_true",
        help="do not fall back to fixtures when crawl is empty",
    )
    args = p.parse_args(argv)
    run(
        args.date,
        allow_fixture=not args.no_fixture,
        force_fixture=args.fixture,
    )
    return 0


if __name__ == "__main__":
    # Allow both `python -m crawler.run` and `python crawler/run.py`
    if __package__ is None:
        sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
