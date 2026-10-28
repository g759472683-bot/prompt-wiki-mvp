---
schema_version: "1.0"
id: claim:zero-downtime-migration
type: claim
title: "账务平台迁移全程零故障（存疑）"
summary: "简历中的绝对化表述，已被复盘 P1 记录推翻，未裁决"
status: active
language: zh-CN
revision: 2
created_at: 2026-10-20T09:42:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
statement: "账务平台迁移全程零故障。"
claim_kind: technical
scope: "仅代表简历自述；与复盘记录冲突，裁决前不得在面试中直接使用。"
verification: verified
tags: [migration, disputed]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-21T20:15:00+08:00
  review_run: run-20261021-01
freshness:
  valid_from: null
  valid_until: null
  review_after: 2026-11-15
confidence:
  level: red
  reasons: [open_conflict]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0004
    quote: "迁移全程零故障"
    role: primary
    verified: true
conflicts: ["cfl-01JCF8Q4R6T2W8Y4B6D2F8H1K3"]
conflict_state: open
---

# 账务平台迁移全程零故障（存疑）

## 一句话说法

这句话来自简历原文（E1），但 2025-09-18 的复盘记录了当晚的 P1，因此它**当前不成立**，不能作为回答依据。

## 成立条件

- 曾经成立的前提：只统计"迁移切换窗口"且不含对账链路。
- 现在不成立：复盘记录的时间线覆盖 22:10–02:05，定级 P1。
- 对外口径：等冲突裁决后决定是改写为"迁移切换本身未中断交易，但对账链路出现 P1"。

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:resume-2026]] · b-0004：「迁移全程零故障」

## 可能的反驳

- 问：简历是你自己写的，为什么和复盘矛盾？ → 答：简历写于事故前，复盘是事后材料，以复盘为准。
- 问：那到底有没有故障？ → 答：有，P1，4 小时 12 分，见 [[story:ledger-migration-2025|案例]]。
