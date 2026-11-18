---
title: "「万字长文」大模型异步 RL 框架的设计与权衡：从 Staleness 控制谈起"
date: 2026-11-18
source: "智源社区"
source_id: baai
url: "https://hub.baai.ac.cn/view/59795"
summary: "PSRL是一种面向大语言模型（LLM）异步强化学习（RL）后训练的staleness可控框架，旨在缓解异步更新中策略延迟（staleness）导致的训练不稳定与性能下降问题。该框架通过动态调节旧策略样本的权重、引入时间感知的梯度裁剪及staleness感知的采样机制，实现对延迟效应的显式建模与抑制。实验表明，PSRL在多个LLM RLHF任务上显著提升收敛速度与最终效果，兼顾训练效率与稳定性。项目已开源，支持灵活集成至现有RLHF流程。"
tags:
  - AI
article_id: 60e3ceb772a1db8c
---

本页为资讯索引，完整报道请阅读原文。
