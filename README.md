# D-Ai-ly

中文 AI / 科技资讯日更 blog。从六家公开媒体抓取当日标题与摘要，生成「今日速报」与单篇索引，部署到 GitHub Pages。

**站点：** https://gebilxs.github.io/D-Ai-ly/

## 信息源

- [机器之心](https://www.jiqizhixin.com/)（官网；当前多为数据服务墙）· [跳转官方微博](https://weibo.com/synced)
- [量子位](https://www.qbitai.com/)
- [极客公园](https://www.geekpark.net/)
- [甲子光年](https://www.jazzyear.com/)
- [新智元](https://www.sina.cn/media/5703921756)
- [智源社区](https://hub.baai.ac.cn/)

本站只索引标题、摘要与原文链接，不转载全文。

## 本地开发

```bash
pip install -r requirements.txt
npm install

# 检查 README / 站点上展示的六个源官网链接
python3 -m crawler.check_homepages
# 报告写入 crawler/homepage_check_report.json

# 检查爬虫端点（条目数 + 样本原文链接 HTTP 探测）
python3 -m crawler.check_sources
# 报告写入 crawler/source_check_report.json

# 抓取当天（只写真实源；抓不到则为空）
python3 -m crawler.run --date today
# 本地调试才用 demo（example.com，不会进生产）
python3 -m crawler.run --fixture

npm run dev
# 构建
npm run build
```

## 自动更新

GitHub Actions 工作流 [`.github/workflows/daily.yml`](.github/workflows/daily.yml)：

- **每小时**整点运行一次（`cron: 0 * * * *`，UTC）
- 也可在 Actions 页手动 `workflow_dispatch`
- 流程：源健康检查 → 爬取 → 写入 `src/content/` → `astro build` → 部署 Pages → 回写新增内容到 `main`
- 源检查报告作为 artifact：`link-check-reports`
- 文章日期以 RSS `pubDate`（转上海时区）为准；RSS 正常但当日无新稿时不再用首页「N小时前」兜底，避免把昨天的稿打进今天
- 新智元（sina 短链）带绝对日期的旧帖不会再被「今天/小时前」相对时间重打成今天；已入库的旧文也不会被写进新的日更
- 本地校验：`python3 -m crawler.test_date_bucketing`；若日更被污染可跑 `python3 -m crawler.rebuild_digests`

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

## 机器之心 Cookie（可选）

官网资讯页需要登录会话。把浏览器里的 `Cookie` 整段放进环境变量 **`JIQIZHIXIN_COOKIE`**（不要写进代码或 commit）：

1. 浏览器登录 [jiqizhixin.com](https://www.jiqizhixin.com/)，打开开发者工具 → Network → 任选请求 → 复制 Request Headers 里的 `Cookie`
2. **本地：** `export JIQIZHIXIN_COOKIE='...'` 后运行爬虫  
3. **GitHub Actions：** Settings → Secrets → Actions → 新建 `JIQIZHIXIN_COOKIE`

未配置或 Cookie 失效时，会回退到机器之心官方微博。

## 微博 Cookie（可选，救微博回退链路）

m.weibo.cn 的容器接口对匿名/数据中心 IP 请求返回 **432 反爬**，导致机器之心的微博回退拿不到数据。配置 **`MWEIBO_COOKIE`** 后恢复：

1. 浏览器登录 [m.weibo.cn](https://m.weibo.cn/)，开发者工具 → Network → 任选 `m.weibo.cn` 请求 → 复制 Request Headers 里的 `Cookie`（关键项是 `SUB=...`）
2. **本地：** `export MWEIBO_COOKIE='...'`
3. **GitHub Actions：** Settings → Secrets → Actions → 新建 `MWEIBO_COOKIE`

两个 Cookie 都会过期（约每月一次）。过期时 coverage 步骤会在 Actions Summary 里把该源标为空转告警，更新 Secret 即可恢复。

## 安全提醒

- 若曾将 GitHub PAT / 登录 Cookie 粘贴到聊天或日志中，请立刻撤销并重新登录签发；**切勿把密钥提交进代码**。
- 仓库与 Actions 仅使用 `GITHUB_TOKEN`；机器之心 Cookie 只放在 Secret / 本地环境变量。
