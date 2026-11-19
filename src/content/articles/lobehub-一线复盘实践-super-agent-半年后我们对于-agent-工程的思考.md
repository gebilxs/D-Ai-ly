---
title: "LobeHub 一线复盘：实践 Super-Agent 半年后，我们对于 Agent 工程的思考"
date: 2026-11-19
source: "智源社区"
source_id: baai
url: "https://hub.baai.ac.cn/view/59827"
summary: "本文为LobeHub团队在多人协作场景下落地Super-agent的工程复盘。不同于单人聊天框中的双层Agent调度，团队将多模型Agent嵌入Discord频道与任务看板，与人类混编协同研发。实践发现，仅依赖Session机制无法满足跨成员、跨任务、长周期的上下文一致性与状态隔离需求，必须构建独立的Agent运行时环境，以支撑身份识别、权限控制、状态持久化及协作审计等关键能力。"
tags:
  - AI
article_id: b71b9ac4aea3135c
---

本页为资讯索引，完整报道请阅读原文。
