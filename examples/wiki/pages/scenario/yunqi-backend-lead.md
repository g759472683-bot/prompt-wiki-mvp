---
schema_version: "1.0"
id: scenario:yunqi-backend-lead
type: scenario
title: "云栖科技 · 后端负责人面试"
summary: "2026-11-03 14:00，60 分钟，CTO + HRBP，目标拿 offer"
status: active
language: zh-CN
revision: 2
created_at: 2026-10-20T10:00:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: human:lin
run_id: run-20261025-02
scenario_kind: interview
counterparty: entity:yunqi-tech
scheduled_at: 2026-11-03T14:00:00+08:00
duration_min: 60
goal: "拿到后端负责人 offer，重点证明高并发交易与团队管理"
audience: ["CTO 陈默", "HRBP 周岚"]
questions:
  - {qa: "qa:why-this-role", priority: 1, must_hit: true, note: "开场必问，决定第一印象"}
  - {qa: "qa:biggest-failure", priority: 1, must_hit: true, note: "诚实度测试，不能用绝对化表述"}
  - {qa: "qa:migration-architecture", priority: 2, must_hit: false, note: "技术深挖，可能追问分片键"}
constraints:
  do_not_claim:
    - "不要承诺 3 个月内重构实时链路"
    - "不要绝对化描述那次 P1"
    - "不要承诺具体涨幅"
  must_mention:
    - "8 人团队管理经验"
    - "2025 年 P1 的复盘与改进"
prepared_at: 2026-10-24T21:30:00+08:00
prep_run: run-20261024-01
tags: [interview, yunqi]
---

# 云栖科技 · 后端负责人面试

## 会前简报

[[entity:yunqi-tech|云栖科技]]是企业级数据平台服务商，2024 年营收 6.8 亿元、员工约 700 人，岗位汇报 CTO、管理 12 人团队。这次见 CTO 陈默和 HRBP 周岚，60 分钟。对方最在意两件事：能不能扛住实时链路的 P99 目标（200ms），以及有没有带团队打过硬仗。我的短板是实时数仓经验，必须用支付账务的一致性经验做迁移，而不是装懂。

## 对方关注点

- 高并发交易系统的一致性经验（对应 [[qa:migration-architecture|迁移架构]]）。
- 团队管理：8 人团队怎么带、怎么处理事故责任（对应 [[qa:biggest-failure|最大失败]]）。
- 动机：为什么从支付转数据平台，能不能长期做（对应 [[qa:why-this-role|为什么选择云栖]]）。

## 我的三个目标

1. 让 CTO 记住"账务一致性 + 迁移"这两个标签。
2. 问清实时链路的现状、团队分工、P99 目标的拆解方式。
3. 不承诺做不到的时间点，不用绝对化表述。

## 风险与禁区

- 最大风险是"最大失败"这题：简历与复盘的冲突还没裁决，必须按复盘口径说，先兜底再展开。
- 实时数仓没做过，被追问时要承认，不要编概念。
- 薪资只在 HR 环节谈，不做具体承诺。

## 问题清单

| 优先级 | 问题 | 卡片 | 必答 | 备注 |
|---|---|---|---|---|
| 1 | [[qa:why-this-role|为什么选择云栖科技]] | ✅ | 是 | 开场必问 |
| 1 | [[qa:biggest-failure|你最大的失败是什么]] | ✅ | 是 | 诚实度测试 |
| 2 | [[qa:migration-architecture|分库迁移怎么做的]] | ✅ | 否 | 技术深挖 |
