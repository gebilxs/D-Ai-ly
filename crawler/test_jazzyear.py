#!/usr/bin/env python3
"""Regression tests: jazzyear byline date parsing & high-water discovery.

Locked-down behaviors:
- publish date comes from the byline footer anchor (class="time"), never
  from related-article dates (class="time font-12") that appear earlier
- high-water discovery reaches the true newest id even when the configured
  start_id is far below it and ids contain gaps
- the scan window starts at the discovered tip itself
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetch import jazzyear  # noqa: E402

FIXTURE = ROOT / "crawler" / "fixtures" / "jazzyear_article_sample.html"


class ParseDetailTests(unittest.TestCase):
    def setUp(self):
        self.html = FIXTURE.read_text(encoding="utf-8")

    def test_publish_date_from_byline_anchor(self):
        title, pub = jazzyear._parse_detail(self.html)
        self.assertEqual(title, "AI终端走进物理世界，需要一颗怎样的芯片？")
        self.assertEqual(pub, date(2026, 7, 20))

    def test_related_article_dates_never_picked(self):
        # If the byline anchor regresses to "first date anywhere", this
        # fixture would return a 2099 related-article date instead.
        _, pub = jazzyear._parse_detail(self.html)
        self.assertNotEqual(pub, date(2099, 12, 31))

    def test_byline_date_found_beyond_old_12k_window(self):
        # Insert filler after <title> so the byline sits far past the old
        # 12k head cut while the title stays within it.
        marker = '<div class="article-footer">'
        padded = self.html.replace(
            marker, "<div>filler</div>" * 1200 + marker, 1
        )
        self.assertGreater(padded.index('class="author'), 12000)
        _, pub = jazzyear._parse_detail(padded)
        self.assertEqual(pub, date(2026, 7, 20))

    def test_empty_or_wall_page_rejected(self):
        self.assertEqual(jazzyear._parse_detail(""), (None, None))
        self.assertEqual(jazzyear._parse_detail("<html></html>"), (None, None))


def _fake_probe(existing: set[int], dates: dict[int, date | None] | None = None):
    dates = dates or {}

    def probe(aid: int, cache=None):
        if aid not in existing:
            return None
        url = f"https://www.jazzyear.com/article_info.html?id={aid}"
        return (url, f"文章{aid}", dates.get(aid))

    return probe


class HighWaterTests(unittest.TestCase):
    def test_discovers_tip_far_above_stale_start(self):
        # start 1700, dense ids 1712-1837, real tip 1837, 1838+ missing
        existing = set(range(1700, 1712)) | set(range(1712, 1838))
        with mock.patch.object(jazzyear, "_probe_id", side_effect=_fake_probe(existing)):
            self.assertEqual(jazzyear._find_high_water(1700), 1837)

    def test_tolerates_mid_range_gaps(self):
        # gap of 8 (1712-1719 missing) must not stop discovery
        existing = set(range(1700, 1712)) | set(range(1720, 1838))
        with mock.patch.object(jazzyear, "_probe_id", side_effect=_fake_probe(existing)):
            self.assertEqual(jazzyear._find_high_water(1700), 1837)

    def test_returns_floor_when_nothing_parses(self):
        with mock.patch.object(jazzyear, "_probe_id", side_effect=_fake_probe(set())):
            self.assertEqual(jazzyear._find_high_water(1700), 900)


class ScanTests(unittest.TestCase):
    def test_scan_includes_tip_and_filters_by_date(self):
        today = date(2026, 8, 21)
        existing = set(range(1798, 1838))
        dates = {1837: today, 1836: date(2026, 8, 13), 1835: date(2026, 8, 12)}
        with mock.patch.object(
            jazzyear, "_probe_id", side_effect=_fake_probe(existing, dates)
        ):
            arts = jazzyear.fetch_jazzyear_scan(
                source_id="jazzyear",
                source_name="甲子光年",
                target=today,
                date_filter=True,
                start_id=1830,
                scan=40,
            )
        urls = [a.url for a in arts]
        # tip itself must be scanned (old code started at high+3 and lost it)
        self.assertTrue(any("id=1837" in u for u in urls))
        self.assertEqual(len(arts), 1)
        self.assertEqual(arts[0].published, "2026-08-21")

    def test_no_date_order_early_stop(self):
        # id 1837 is old, id 1835 is today: an "older-streak" early stop
        # walking down from the tip would drop today's article.
        today = date(2026, 8, 12)
        existing = set(range(1798, 1838))
        dates = {1837: date(2026, 8, 21), 1836: date(2026, 8, 13), 1835: today}
        with mock.patch.object(
            jazzyear, "_probe_id", side_effect=_fake_probe(existing, dates)
        ):
            arts = jazzyear.fetch_jazzyear_scan(
                source_id="jazzyear",
                source_name="甲子光年",
                target=today,
                date_filter=True,
                start_id=1830,
                scan=40,
            )
        self.assertEqual([a.published for a in arts], ["2026-08-12"])


if __name__ == "__main__":
    unittest.main()
