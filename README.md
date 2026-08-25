# D-Ai-ly

Daily Chinese AI news digest. Crawls six public media sources every hour, publishes a daily digest plus per-article index pages, deployed to GitHub Pages.

**Site:** https://gebilxs.github.io/D-Ai-ly/

## Sources

[Jiqizhixin](https://www.jiqizhixin.com/) · [QbitAI](https://www.qbitai.com/) · [Geekpark](https://www.geekpark.net/) · [Jiazi Guangnian](https://www.jazzyear.com/) · [Xinzhiyuan](https://www.sina.cn/media/5703921756) · [BAAI Hub](https://hub.baai.ac.cn/)

Titles, summaries, and links to the original articles only.

## Local development

```bash
pip install -r requirements.txt
npm install

python3 -m crawler.run --date today   # crawl today
python3 -m crawler.check_sources     # source health check
python3 -m crawler.coverage          # per-source coverage report

npm run dev                          # dev server
npm run build                        # build
```

## Deployment

GitHub Actions (`.github/workflows/daily.yml`) runs hourly: crawl → build → deploy to Pages → commit new content back to `main`.

## Optional secrets

- `JIQIZHIXIN_COOKIE` — logged-in session for jiqizhixin.com
- `MWEIBO_COOKIE` — logged-in m.weibo.cn cookie (fixes the 432 anti-crawl fallback)

Both expire roughly monthly; update them in Settings → Secrets → Actions.
