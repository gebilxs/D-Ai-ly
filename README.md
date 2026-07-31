# D-Ai-ly

中文 AI / 科技资讯日更 blog。从六家公开媒体抓取当日标题与摘要，生成「今日速报」与单篇索引，部署到 GitHub Pages。

**站点：** https://gebilxs.github.io/D-Ai-ly/

## 信息源

- [机器之心](https://www.jiqizhixin.com/)
- [量子位](https://www.qbitai.com/)
- [甲子光年](https://www.jazzyear.com/index.html)
- [极客公园](https://www.geekpark.net/)
- [新浪媒体号](https://www.sina.cn/media/5703921756)
- [智源社区](https://hub.baai.ac.cn/)

本站只索引标题、摘要与原文链接，不转载全文。

## 本地开发

```bash
pip install -r requirements.txt
npm install

# 抓取当天（外网不可达时自动回落 fixtures）
python3 crawler/run.py --date today
# 或强制 demo 数据
python3 crawler/run.py --fixture

npm run dev
# 构建
npm run build
```

## 自动更新

GitHub Actions 工作流 [`.github/workflows/daily.yml`](.github/workflows/daily.yml)：

- 每天 UTC 00:00（北京时间约 08:00）定时运行
- 也可在 Actions 页手动 `workflow_dispatch`
- 流程：爬取 → 写入 `src/content/` → `astro build` → 部署 Pages → 回写新增内容到 `main`

### 开启 Pages（首次必做一次）

Actions 会把站点推到 `gh-pages` 分支。首次请手动：

1. 打开 **Settings → Pages**
2. **Build and deployment → Source** 选 **Deploy from a branch**
3. Branch 选 **`gh-pages`** / **`/ (root)`** → Save
4. 等 1–2 分钟后访问：https://gebilxs.github.io/D-Ai-ly/

## 目录

```
crawler/           # Python 六源抓取
src/content/       # articles + digests（Markdown）
src/pages/         # Astro 页面
.github/workflows/ # 日更与部署
```

## 安全提醒

若曾将 GitHub Personal Access Token 粘贴到聊天或日志中，请立刻到 GitHub 撤销并重新签发；仓库与 Actions 仅使用 `GITHUB_TOKEN`，切勿把 PAT 提交进代码。
