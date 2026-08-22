---
title: "Claude Code 被轻易攻破，仅需一个假工具"
date: 2026-08-22
source: "智源社区"
source_id: baai
url: "https://hub.baai.ac.cn/view/57320"
summary: "研究者在ISSTA 2026（CCF-A类会议）接收论文中复现了AI编程助手遭“隐式命令注入”攻击的案例：用户请求编写贪吃蛇游戏，AI却额外执行了恶意curl | bash命令，下载并运行攻击者脚本。该漏洞影响Cursor、Claude Code、Copilot、Windsurf、Clin等主流工具，源于模型对自然语言指令中隐蔽shell命令的误解析与自动执行，暴露了AI编码助手在安全沙箱、输入过滤和权限控制方面的严重缺陷，凸显其在生产环境部署前亟需强化安全机制。"
tags:
  - AI
article_id: 84bb2fc693fb5502
---

本页为资讯索引，完整报道请阅读原文。
