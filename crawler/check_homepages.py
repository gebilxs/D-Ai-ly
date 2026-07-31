#!/usr/bin/env python3
"""Deterministic check for the six source homepage links shown on GitHub / the site.

These are the public URLs in src/lib/sources.ts and README — not crawl endpoints.
Exit 1 if any homepage fails.
Writes crawler/homepage_check_report.json
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.httputil import url_ok  # noqa: E402

SOURCES_TS = ROOT / "src" / "lib" / "sources.ts"
README = ROOT / "README.md"
REPORT_PATH = Path(__file__).resolve().parent / "homepage_check_report.json"

# Soft-404 / wall signatures for known broken homepages
_WALLS = (
    ("jiqizhixin.com", "数据服务已上线"),
    ("jiqizhixin.com", "机器之心·数据服务"),
)


@dataclass
class HomeReport:
    id: str
    name: str
    url: str
    ok: bool
    detail: str = ""
    errors: list[str] = field(default_factory=list)


def load_display_sources() -> list[dict[str, str]]:
    text = SOURCES_TS.read_text(encoding="utf-8")
    # Support single-line and multi-line objects (with // comments between fields).
    out: list[dict[str, str]] = []
    for block in re.split(r"\}\s*,\s*\{", text):
        sid = re.search(r'id:\s*"([^"]+)"', block)
        name = re.search(r'name:\s*"([^"]+)"', block)
        url = re.search(r'url:\s*"([^"]+)"', block)
        if sid and name and url:
            out.append({"id": sid.group(1), "name": name.group(1), "url": url.group(1)})
    if len(out) < 6:
        raise RuntimeError(f"expected 6 display sources, parsed {len(out)}")
    return out


def readme_urls() -> list[str]:
    text = README.read_text(encoding="utf-8")
    # only the 信息源 section links
    section = re.search(r"## 信息源\n(.*?)(?:\n## |\Z)", text, re.S)
    if not section:
        return []
    return re.findall(r"\((https?://[^)]+)\)", section.group(1))


def check_wall(url: str, body_hint: str) -> str | None:
    for host, marker in _WALLS:
        if host in url and marker in body_hint:
            return f"homepage is login/data wall ({marker})"
    return None


def main() -> int:
    sources = load_display_sources()
    reports: list[HomeReport] = []
    for s in sources:
        r = HomeReport(id=s["id"], name=s["name"], url=s["url"], ok=False)
        ok, detail = url_ok(s["url"], timeout=20.0)
        r.detail = detail
        if not ok:
            r.errors.append(detail)
        else:
            # fetch body snippet for wall detection
            try:
                from crawler.httputil import fetch_text

                body = fetch_text(s["url"], timeout=20.0)[:3000]
                wall = check_wall(s["url"], body)
                if wall:
                    r.errors.append(wall)
                    r.detail = wall
            except Exception as e:
                # url_ok already passed; wall check best-effort
                r.detail = f"{detail}; wall-check skipped: {e}"
        r.ok = len(r.errors) == 0
        reports.append(r)

    ts_urls = {s["url"].rstrip("/") for s in sources}
    md_urls = {u.rstrip("/") for u in readme_urls()}
    sync_errors: list[str] = []
    if md_urls != ts_urls:
        only_md = sorted(md_urls - ts_urls)
        only_ts = sorted(ts_urls - md_urls)
        if only_md:
            sync_errors.append(f"README-only urls: {only_md}")
        if only_ts:
            sync_errors.append(f"sources.ts-only urls: {only_ts}")

    payload = {
        "ok": all(r.ok for r in reports) and not sync_errors,
        "passed": sum(1 for r in reports if r.ok),
        "failed": [r.id for r in reports if not r.ok],
        "sync_errors": sync_errors,
        "sources": [asdict(r) for r in reports],
    }
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("\n=== Homepage Summary ===")
    for r in reports:
        print(f"[{'PASS' if r.ok else 'FAIL'}] {r.id:12} {r.url}")
        for e in r.errors:
            print(f"         - {e}")
    for e in sync_errors:
        print(f"[SYNC] {e}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
