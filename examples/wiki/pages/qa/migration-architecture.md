---
schema_version: "1.0"
id: qa:migration-architecture
type: qa
title: "分库迁移怎么做的"
summary: "商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务"
status: active
language: zh-CN
revision: 2
created_at: 2026-10-20T09:52:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
question: "账务平台的分库迁移是怎么做的？"
question_variants:
  - "讲讲你那个分库分表项目"
  - "2.3 亿笔怎么迁的"
  - "迁移方案怎么设计的"
  - "分片键为什么选商户 ID"
intent: technical
scenario_kinds: [interview]
answer:
  target_sec: 90
  tone: confident
tags: [migration, architecture]
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
  reasons: [two_sources, no_conflict, human_reviewed, fresh, refs_green]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence_refs:
  - claim:ledger-migration-led
conflicts: []
conflict_state: none
card:
  l1: ["商户 ID 分片", "双写 6 周", "灰度放量", "2.3 亿笔/日"]
  l2:
    - "账务 12 个服务，按商户 ID 分片"
    - "双写 6 周，灰度放量切换"
    - "日均 2.3 亿笔，迁移由我牵头"
  fallback: "细节我要翻迁移方案再确认；确定的是商户 ID 分片、双写 6 周、覆盖 12 个服务。"
  evidence_refs:
    - claim:ledger-migration-led
  confidence:
    level: green
    reasons: [two_sources, no_conflict, human_reviewed, fresh, refs_green]
    rule: rule_v1
    computed_at: 2026-10-25T10:20:00+08:00
  built_from:
    - {id: "claim:ledger-migration-led", revision: 3}
  do_not_say: ["零故障", "完全没影响"]
---

# 分库迁移怎么做的

## 一句话回答

核心是分片键选商户 ID：同一商户的账务落在一个分片里，减少跨分片事务；然后双写 6 周校验一致性，再灰度放量，覆盖 12 个服务、日均 2.3 亿笔（E1）。

## 展开

第一步选分片键。账务查询几乎都带商户维度，用商户 ID 分片能把一个商户的记账、清分、对账放在同一分片，跨分片事务最少。第二步双写 6 周，新旧库同时写，用对账任务比对差异，差异清零才进下一步。第三步灰度放量，按流量比例逐步切，保留回滚能力。整个迁移由我牵头，复盘也确认了架构方案没有问题（E2）。

## 证据

<!-- 由编译器从 evidence_refs 解析生成，人工勿改 -->
- E1 · [[claim:ledger-migration-led]] · [[source:resume-2026]] · b-0004：「主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易」
- E2 · [[claim:ledger-migration-led]] · [[source:postmortem-2025]] · b-0005：「迁移由林舟牵头，架构方案无问题」

## 边界与不知道

- 具体双写延迟数字、每个服务的放量节奏，我需要翻方案文档才能给准确值。
- 这次迁移出过 P1（对账补偿任务漏了退款流水），讲方案时不能省略，见 [[qa:biggest-failure|最大失败]]。

## 追问预案

- 问：为什么不用一致性哈希？ → 答：商户 ID 是天然分片键，范围可控、扩容可按商户迁移；一致性哈希解决的是另一类问题。
- 问：双写怎么保证不丢？ → 答：靠对账任务比对，差异清零才放量；补偿任务覆盖所有流水类型是后来补的教训。
