#!/usr/bin/env python3
"""Unit tests for coverage counting logic (digest parsing, empty streaks)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.coverage import counts_by_day, empty_streak  # noqa: E402

_DIGEST_TMPL = """---
title: "今日 AI 速报 · {d}"
date: {d}
count: {n}
items:
  - title: "t1"
    slug: s1
    source: 量子位
    source_id: qbitai
    url: "https://example.com/1"
    summary: ""
  - title: "t2"
    slug: s2
    source: 智源社区
    source_id: baai
    url: "https://example.com/2"
    summary: ""
---
正文里不会出现 source_id 字样。
"""


class CoverageTests(unittest.TestCase):
    def test_counts_and_streak(self):
        with tempfile.TemporaryDirectory() as td:
            droot = Path(td)
            today = date(2026, 8, 24)
            days = [today - timedelta(days=i) for i in range(4, 0, -1)]
            # qbitai has items every day; baai empty the last 3 days
            baai_item = (
                '  - title: "t2"\n    slug: s2\n    source: 智源社区\n'
                '    source_id: baai\n    url: "https://example.com/2"\n'
                '    summary: ""\n'
            )
            for d in days:
                text = _DIGEST_TMPL.format(d=d.isoformat(), n=2)
                if d >= today - timedelta(days=3):
                    text = text.replace(baai_item, "")
                (droot / f"{d.isoformat()}.md").write_text(text, encoding="utf-8")
            counts = counts_by_day(days, droot)

            self.assertEqual(counts[days[0].isoformat()], {"qbitai": 1, "baai": 1})
            self.assertEqual(counts[days[-1].isoformat()], {"qbitai": 1})
            self.assertEqual(empty_streak(counts, "qbitai"), 0)
            self.assertEqual(empty_streak(counts, "baai"), 3)

    def test_missing_digest_counts_as_empty(self):
        with tempfile.TemporaryDirectory() as td:
            days = [date(2026, 8, 23), date(2026, 8, 22)]
            counts = counts_by_day(days, Path(td))
            self.assertEqual(empty_streak(counts, "qbitai"), 2)

    def test_body_text_not_counted(self):
        with tempfile.TemporaryDirectory() as td:
            droot = Path(td)
            d = date(2026, 8, 23)
            (droot / f"{d.isoformat()}.md").write_text(
                _DIGEST_TMPL.format(d=d.isoformat(), n=2), encoding="utf-8"
            )
            counts = counts_by_day([d], droot)
            # only the two frontmatter items, body prose adds nothing
            self.assertEqual(counts[d.isoformat()], {"qbitai": 1, "baai": 1})


if __name__ == "__main__":
    unittest.main()
