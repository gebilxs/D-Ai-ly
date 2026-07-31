from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ..httputil import host_reachable
from ..models import Article
from .html import enrich_summary_from_page, fetch_html_list
from .rss import fetch_rss

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


def fetch_source(
    src: dict[str, Any], target: date
) -> tuple[list[Article], list[dict[str, Any]]]:
    sid = src["id"]
    name = src["name"]
    kind = src.get("kind", "html")
    errors: list[dict[str, Any]] = []
    arts: list[Article] = []

    if kind == "rss":
        url = src.get("url") or ""
        if not host_reachable(url):
            errors.append(
                {
                    "source_id": sid,
                    "stage": "rss",
                    "url": url,
                    "error": "host unreachable (preflight)",
                }
            )
        else:
            try:
                arts = fetch_rss(
                    url, source_id=sid, source_name=name, target=target
                )
            except Exception as e:
                errors.append(
                    {
                        "source_id": sid,
                        "stage": "rss",
                        "url": url,
                        "error": f"{type(e).__name__}: {e}",
                    }
                )
        if not arts:
            fallback = src.get("html_fallback")
            if fallback:
                if not host_reachable(fallback):
                    errors.append(
                        {
                            "source_id": sid,
                            "stage": "html_fallback",
                            "url": fallback,
                            "error": "host unreachable (preflight)",
                        }
                    )
                else:
                    try:
                        arts = fetch_html_list(
                            fallback,
                            source_id=sid,
                            source_name=name,
                            target=target,
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

    url = src.get("url") or ""
    if not host_reachable(url):
        errors.append(
            {
                "source_id": sid,
                "stage": "html",
                "url": url,
                "error": "host unreachable (preflight)",
            }
        )
        return arts, errors
    try:
        arts = fetch_html_list(
            url, source_id=sid, source_name=name, target=target
        )
    except Exception as e:
        errors.append(
            {
                "source_id": sid,
                "stage": "html",
                "url": url,
                "error": f"{type(e).__name__}: {e}",
            }
        )
    return arts, errors


def fetch_all(
    target: date,
    *,
    sources_path: Path | None = None,
    enrich: bool = True,
) -> tuple[list[Article], list[dict[str, Any]]]:
    sources = load_sources(sources_path)
    all_arts: list[Article] = []
    all_errors: list[dict[str, Any]] = []
    for src in sources:
        arts, errs = fetch_source(src, target)
        all_arts.extend(arts)
        all_errors.extend(errs)
    deduped = _dedupe(all_arts)
    if enrich:
        for art in deduped:
            if not art.summary:
                art.summary = enrich_summary_from_page(art.url)
    return deduped, all_errors
