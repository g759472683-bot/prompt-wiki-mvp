---
schema_version: "1.0"
id: metric:availability-2025
type: metric
title: "账务平台 2025 年度可用性"
summary: "简历口径 99.99%，复盘口径 99.95%，冲突未决"
status: active
language: zh-CN
revision: 2
created_at: 2026-10-20T09:45:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
metric:
  name: "账务平台年度可用性"
  key: "availability"
  value: "99.99%"
  value_num: 99.99
  unit: "%"
  direction: higher
  period: "2025"
  method: "按分钟不可用时长 / 全年分钟数，剔除计划内维护"
  scope: "星桥支付账务平台"
tags: [availability, disputed]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-21T20:18:00+08:00
  review_run: run-20261021-01
freshness:
  valid_from: 2025-01-01
  valid_until: 2026-12-31
  review_after: 2026-11-30
confidence:
  level: red
  reasons: [open_conflict]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0005
    quote: "账务平台年度可用性 99.99%"
    role: primary
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0006
    quote: "2025 年度可用性 99.95%，未达 99.99% 目标"
    role: counter
    verified: true
conflicts: ["cfl-01JCF7P3T2M8N4R6W9Y1B5D7F3"]
conflict_state: open
---

# 账务平台 2025 年度可用性

## 口径

统计 2025 自然年，按分钟不可用时长除以全年分钟数，剔除计划内维护。简历写 99.99%（E1），复盘写 99.95%（E2），两者都是"年度"口径，因此构成冲突。

## 计算方式

`可用性 = 1 - 不可用分钟数 / (365 × 24 × 60)`；不可用定义：核心记账接口 5 分钟窗口错误率 >5%。

## 为什么可信

- 来源都是高信任：简历由我撰写，复盘由我根据监控与财务对账撰写。
- 但两个数字不一致，已在 `cfl-01JCF7P3T2M8N4R6W9Y1B5D7F3` 挂起，等待与监控原始报表核对。
- **裁决前对外只说"复盘口径 99.95%"，不说 99.99%**。

## 常见追问

- 问：到底是 99.99 还是 99.95？ → 答：以复盘和监控为准是 99.95%，简历那个数需要更正。
- 问：为什么差这么多？ → 答：一次 P1 就足以把年度可用性拉下 0.04 个点，正在核对原始报表。

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:resume-2026]] · b-0005：「账务平台年度可用性 99.99%」
- E2 · [[source:postmortem-2025]] · b-0006：「2025 年度可用性 99.95%，未达 99.99% 目标」
