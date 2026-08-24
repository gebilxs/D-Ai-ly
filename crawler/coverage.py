#!/usr/bin/env python3
"""Per-source coverage report & alert.

Reads the recent daily digests, computes how many consecutive days each
source contributed 0 items (counting back from yesterday — today is
still accumulating hourly), writes crawler/stats.json, appends a
Markdown table to $GITHUB_STEP_SUMMARY when run in Actions, and exits 1
when a source exceeds its check.alert_empty_days threshold.

This is the tripwire that was missing when three sources silently
produced nothing for weeks: the crawl step stays continue-on-error so a
flaky network never blocks deploys, while this step turns persistent
per-source emptiness into a red run.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetch.dates import today_shanghai  # noqa: E402
from crawler.fetch.pipeline import load_sources  # noqa: E402

DIGESTS_DIR = ROOT / "src" / "content" / "digests"
STATS_PATH = Path(__file__).resolve().parent / "stats.json"
WINDOW_DAYS = 7
DEFAULT_ALERT_DAYS = 2

# Digest frontmatter item fields are the only indented `source_id:` lines.
_ITEM_RE = re.compile(r"^\s+source_id:\s*(\S+)\s*$", re.M)


def counts_by_day(
    days: list[date], digests_dir: Path = DIGESTS_DIR
) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for d in days:
        path = digests_dir / f"{d.isoformat()}.md"
        per: dict[str, int] = {}
        if path.exists():
            per = dict(Counter(_ITEM_RE.findall(path.read_text(encoding="utf-8"))))
        out[d.isoformat()] = per
    return out


def empty_streak(day_counts: dict[str, dict[str, int]], sid: str) -> int:
    """Consecutive empty days from the newest day backwards.

    A day without a digest file counts as empty for every source — a
    fully dead pipeline must trip the alert too.
    """
    streak = 0
    for day in sorted(day_counts, reverse=True):
        if day_counts[day].get(sid, 0) > 0:
            break
        streak += 1
    return streak


def main() -> int:
    today = today_shanghai()
    days = [today - timedelta(days=i) for i in range(WINDOW_DAYS, 0, -1)]
    day_counts = counts_by_day(days)

    rows = []
    breaches: list[tuple[str, str, int, int]] = []
    for src in load_sources():
        sid = src["id"]
        cfg = src.get("check") or {}
        alert_days = int(cfg.get("alert_empty_days") or DEFAULT_ALERT_DAYS)
        streak = empty_streak(day_counts, sid)
        total = sum(dc.get(sid, 0) for dc in day_counts.values())
        status = "ALERT" if streak >= alert_days else "OK"
        if status == "ALERT":
            breaches.append((sid, src["name"], streak, alert_days))
        rows.append((sid, src["name"], total, streak, alert_days, status))

    stats = {
        "date": today.isoformat(),
        "window_days": WINDOW_DAYS,
        "per_day": day_counts,
        "sources": [
            {
                "id": sid,
                "name": name,
                "items_7d": total,
                "empty_streak_days": streak,
                "alert_empty_days": alert_days,
                "status": status,
            }
            for sid, name, total, streak, alert_days, status in rows
        ],
    }
    STATS_PATH.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "## 爬取覆盖情况（近 7 天，不含今天）",
        "",
        "| 来源 | 7天条数 | 连续空缺天数 | 告警阈值 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for sid, name, total, streak, alert_days, status in rows:
        lines.append(f"| {name} ({sid}) | {total} | {streak} | {alert_days} | {status} |")
    summary = "\n".join(lines)
    print(summary)

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(summary + "\n\n")

    if breaches:
        print("\n=== ALERTS (source produced 0 items for too long) ===")
        for sid, name, streak, alert_days in breaches:
            print(f"- {name} ({sid}): 连续 {streak} 天 0 条（阈值 {alert_days}）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
