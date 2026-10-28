---
schema_version: "1.0"
id: entity:ledger-platform
type: entity
title: "账务平台"
summary: "星桥支付的支付账务系统，12 个微服务，我负责 4 年"
status: active
language: zh-CN
revision: 1
created_at: 2026-10-20T09:30:00+08:00
updated_at: 2026-10-20T09:30:00+08:00
created_by: compiler
run_id: run-20261020-01
entity_kind: project
aliases: ["账务平台", "ledger platform"]
tags: [project, payment]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-21T20:12:00+08:00
  review_run: run-20261021-01
freshness:
  valid_from: null
  valid_until: null
  review_after: 2027-04-30
confidence:
  level: yellow
  reasons: [single_source]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0003
    quote: "账务平台包含 12 个微服务：记账、清分、对账、结算、退款等。"
    role: primary
    verified: true
conflicts: []
conflict_state: none
---

# 账务平台

## 一句话定义

星桥支付的支付账务系统，包含 12 个微服务：记账、清分、对账、结算、退款（E1）。它是我过去四年主要的技术载体。

## 关键事实

- 12 个微服务，日均 2.3 亿笔交易（另见 [[claim:ledger-migration-led|分库迁移]]）。
- 2025 年做过分库分表迁移，迁移当晚发生过一次 P1（见 [[story:ledger-migration-2025|迁移案例]]）。

## 与我的关系

我在这里从高级工程师做到技术负责人，带 8 人团队，负责五年。面试里所有硬核案例都来自这个平台。

## 关联页面

- [[claim:ledger-migration-led|分库迁移由我牵头]]
- [[story:ledger-migration-2025|迁移与 P1 复盘]]

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:resume-2026]] · b-0003：「账务平台包含 12 个微服务：记账、清分、对账、结算、退款等。」
