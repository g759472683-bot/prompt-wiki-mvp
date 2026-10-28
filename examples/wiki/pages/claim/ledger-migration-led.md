---
schema_version: "1.0"
id: claim:ledger-migration-led
type: claim
title: "账务平台分库迁移由我牵头"
summary: "我主导了 12 个服务、日均 2.3 亿笔的账务分库迁移，有复盘佐证"
status: active
language: zh-CN
revision: 3
created_at: 2026-10-20T09:40:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
statement: "账务平台分库迁移由我牵头，覆盖 12 个服务、日均 2.3 亿笔交易。"
claim_kind: experience
scope: "适用于回答'你做过最大的技术项目'；不适用于证明迁移过程没有故障。"
verification: verified
tags: [migration, ownership]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-25T10:12:00+08:00
  review_run: run-20261025-02
freshness:
  valid_from: null
  valid_until: null
  review_after: 2027-04-30
confidence:
  level: green
  reasons: [two_sources, no_conflict, human_reviewed, fresh]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0004
    quote: "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易"
    role: primary
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0005
    quote: "迁移由林舟牵头，架构方案无问题"
    role: supporting
    verified: true
conflicts: []
conflict_state: none
---

# 账务平台分库迁移由我牵头

## 一句话说法

2025 年账务平台分库分表是我牵头的：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易（E1）。复盘也确认了牵头人和架构方案（E2）。

## 成立条件

- 成立：迁移范围、规模、牵头人都有两份独立材料可核。
- 不成立的部分：不能由此推出"迁移过程零故障"——当晚发生过 P1，见 [[claim:zero-downtime-migration|这条被推翻的表述]]。
- 对"我个人的贡献"要谨慎：架构评审是团队做的，我负责方案与推进。

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:resume-2026]] · b-0004：「主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易」
- E2 · [[source:postmortem-2025]] · b-0005：「迁移由林舟牵头，架构方案无问题」

## 可能的反驳

- 问：规模这么大，真的是你一个人主导？ → 答：方案和推进是我，评审和落地是 8 人团队，复盘里写的是"牵头"。
- 问：既然你牵头，为什么还出 P1？ → 答：发布检查清单漏了一项，责任在我，具体见案例页。
