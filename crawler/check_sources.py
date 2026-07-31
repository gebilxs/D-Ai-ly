#!/usr/bin/env python3
"""Deterministic health check for every configured source.

Exit code 1 if any non-allow_fail source fails.
Writes crawler/source_check_report.json
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetch.dates import today_shanghai  # noqa: E402
from crawler.fetch.pipeline import fetch_source, load_sources  # noqa: E402
from crawler.httputil import url_ok  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "source_check_report.json"


@dataclass
class SourceReport:
    id: str
    name: str
    kind: str
    ok: bool
    allow_fail: bool = False
    items: int = 0
    sample_titles: list[str] = field(default_factory=list)
    sample_urls: list[str] = field(default_factory=list)
    link_checks: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: str = ""


def _host_ok(url: str, expect: str, alt: str | None = None) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if expect and expect.lower() in host:
        return True
    if alt and alt.lower() in host:
        return True
    # also allow expect in full url (t.cn short links)
    if expect and expect.lower() in url.lower():
        return True
    if alt and alt.lower() in url.lower():
        return True
    return False


def check_one(src: dict[str, Any], target: date) -> SourceReport:
    cfg = src.get("check") or {}
    allow_fail = bool(cfg.get("allow_fail"))
    notes = str(cfg.get("notes") or "")
    report = SourceReport(
        id=src["id"],
        name=src["name"],
        kind=src.get("kind", "?"),
        ok=False,
        allow_fail=allow_fail,
        notes=notes,
    )
    if src.get("enabled") is False:
        report.errors.append(src.get("disabled_reason") or "disabled")
        report.ok = allow_fail
        return report

    # Health check ignores strict "today" filter — need any recent items
    arts, errs = fetch_source(src, target, date_filter=False)
    for e in errs:
        report.errors.append(f"{e.get('stage')}: {e.get('error')} ({e.get('url')})")

    # Prefer items from last 7 days when available
    recent_cut = (today_shanghai() - timedelta(days=7)).isoformat()
    recent = [a for a in arts if a.published >= recent_cut] or arts
    report.items = len(recent)
    report.sample_titles = [a.title for a in recent[:5]]
    report.sample_urls = [a.url for a in recent[:5]]

    min_items = int(cfg.get("min_items") or 1)
    if report.items < min_items:
        report.errors.append(f"items {report.items} < min_items {min_items}")
        report.ok = False
        return report

    expect = str(cfg.get("expect_host") or "")
    alt = cfg.get("alt_expect_host")
    bad_host = []
    for a in recent[:10]:
        if expect and not _host_ok(a.url, expect, alt):
            bad_host.append(a.url)
    if bad_host:
        report.errors.append(f"unexpected hosts: {bad_host[:3]}")
        return report

    probe_n = int(cfg.get("probe_links") or 1)
    for a in recent[:probe_n]:
        ok, detail = url_ok(a.url)
        report.link_checks.append({"url": a.url, "ok": ok, "detail": detail})
        if not ok:
            report.errors.append(f"link check failed: {a.url} ({detail})")

    report.ok = len(report.errors) == 0
    if allow_fail and not report.ok:
        # keep ok False but caller treats as non-blocking
        pass
    return report


def main() -> int:
    target = today_shanghai()
    sources = load_sources()
    reports = [check_one(src, target) for src in sources]
    blocking_fail = [r for r in reports if (not r.ok) and (not r.allow_fail)]
    payload = {
        "date": target.isoformat(),
        "ok": len(blocking_fail) == 0,
        "passed": sum(1 for r in reports if r.ok),
        "failed_blocking": [r.id for r in blocking_fail],
        "failed_soft": [r.id for r in reports if (not r.ok) and r.allow_fail],
        "sources": [asdict(r) for r in reports],
    }
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    print("\n=== Summary ===")
    for r in reports:
        flag = "PASS" if r.ok else ("SOFT-FAIL" if r.allow_fail else "FAIL")
        print(f"[{flag}] {r.id:12} items={r.items} errors={len(r.errors)}")
        for e in r.errors[:3]:
            print(f"         - {e}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
