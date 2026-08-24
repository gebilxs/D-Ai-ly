#!/usr/bin/env python3
"""Regression tests: old posts must not land in today's digest."""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.fetch.sina_weibo import parse_sina_weibo_text  # noqa: E402
from crawler.models import Article  # noqa: E402
from crawler import run as crawl_run  # noqa: E402


SAMPLE_PAGE = """
新智元2026-08-04 09:12来自 微博网页版
今日新稿：某某模型发布了
http://t.cn/NEWpost01
今天 10:01来自 微博网页版
刚发的短帖也算今天
http://t.cn/NEWpost02
新智元2026-08-01 21:28来自 微博网页版
顶，还是北大同班同学。一个竞赛天才，一个高考转系。而就在这几天，AI连破三道数学猜想
http://t.cn/AX99LwEv
小时前 又一条今天的
再来一条相对时间新帖
http://t.cn/NEWpost03
"""


class SinaWeiboDateTests(unittest.TestCase):
    def test_absolute_old_post_not_claimed_by_relative_today(self):
        arts = parse_sina_weibo_text(
            SAMPLE_PAGE,
            source_id="sina_media",
            source_name="新智元",
            target=date(2026, 8, 4),
            date_filter=True,
        )
        urls = {a.url.rstrip("/").lower() for a in arts}
        self.assertNotIn("http://t.cn/ax99lwev", urls)
        self.assertIn("http://t.cn/newpost01", urls)
        # relative-only posts still allowed for today
        self.assertTrue({"http://t.cn/newpost02", "http://t.cn/newpost03"} & urls)

    def test_old_day_filter_keeps_only_that_day(self):
        arts = parse_sina_weibo_text(
            SAMPLE_PAGE,
            source_id="sina_media",
            source_name="新智元",
            target=date(2026, 8, 1),
            date_filter=True,
        )
        urls = [a.url for a in arts]
        self.assertEqual(urls, ["http://t.cn/AX99LwEv"])
        self.assertEqual(arts[0].published, "2026-08-01")


class DigestDedupTests(unittest.TestCase):
    def test_existing_other_day_article_not_added_to_today_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            articles_dir = root / "src" / "content" / "articles"
            digests_dir = root / "src" / "content" / "digests"
            articles_dir.mkdir(parents=True)
            digests_dir.mkdir(parents=True)

            old = articles_dir / "old.md"
            old.write_text(
                "\n".join(
                    [
                        "---",
                        'title: "顶，还是北大同班同学。一个竞赛天才，一个高考转系。而就在这几天，AI连破三道数学猜想"',
                        "date: 2026-08-01",
                        'source: "新智元"',
                        "source_id: sina_media",
                        'url: "http://t.cn/AX99LwEv"',
                        'summary: "old"',
                        "article_id: oldid01",
                        "---",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            fetched = [
                Article(
                    id="oldid01",
                    source_id="sina_media",
                    source_name="新智元",
                    title="顶，还是北大同班同学。一个竞赛天才，一个高考转系。而就在这几天，AI连破三道数学猜想",
                    url="http://t.cn/AX99LwEv",
                    published="2026-08-04",  # mis-dated re-fetch
                    summary="should not enter Aug 4 digest",
                    fetched_via="sina_weibo",
                ),
                Article(
                    id="newid01",
                    source_id="qbitai",
                    source_name="量子位",
                    title="真正的今天新闻",
                    url="https://www.qbitai.com/2026/08/999999.html",
                    published="2026-08-04",
                    summary="ok",
                    fetched_via="rss",
                ),
            ]

            with mock.patch.object(crawl_run, "ROOT", root), mock.patch.object(
                crawl_run, "ARTICLES_DIR", articles_dir
            ), mock.patch.object(crawl_run, "DIGESTS_DIR", digests_dir), mock.patch.object(
                crawl_run, "ERRORS_PATH", root / "last_errors.json"
            ), mock.patch.object(
                crawl_run, "fetch_all", return_value=(fetched, [])
            ):
                result = crawl_run.run("2026-08-04")

            digest = (digests_dir / "2026-08-04.md").read_text(encoding="utf-8")
            self.assertNotIn("AX99LwEv", digest)
            self.assertNotIn("北大同班同学", digest)
            self.assertIn("真正的今天新闻", digest)
            self.assertEqual(result["digest_count"], 1)
            # old article file date must stay Aug 1
            self.assertIn("date: 2026-08-01", old.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())


class EmptyDigestTests(unittest.TestCase):
    def test_new_day_zero_articles_writes_no_digest(self):
        """A day with no articles and no existing digest file must not
        create one: bare `items:` parses as null and fails the Astro
        build (broke the hourly pipeline at Shanghai midnight)."""
        import tempfile
        from datetime import date as date_cls
        from unittest import mock as mock_mod
        from crawler import run as run_mod

        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            with mock_mod.patch.object(run_mod, "ARTICLES_DIR", tdir / "articles"), \
                 mock_mod.patch.object(run_mod, "DIGESTS_DIR", tdir / "digests"), \
                 mock_mod.patch.object(run_mod, "ERRORS_PATH", tdir / "errors.json"), \
                 mock_mod.patch.object(run_mod, "fetch_all", return_value=([], [])):
                result = run_mod.run("2026-08-25")
            self.assertFalse((tdir / "digests" / "2026-08-25.md").exists())
            self.assertEqual(result["digest_count"], 0)
            self.assertEqual(result["digest"], "")
