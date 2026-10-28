---
schema_version: "1.0"
id: qa:biggest-failure
type: qa
title: "你最大的失败是什么"
summary: "2025-09 对账 P1：承认责任、讲清根因、给出改进"
status: active
language: zh-CN
revision: 2
created_at: 2026-10-25T10:12:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
question: "你最大的失败是什么？"
question_variants:
  - "你最大的失败是什么"
  - "说一个你搞砸的事"
  - "你职业生涯最严重的失误"
  - "有没有哪次上线出过大问题"
intent: behavioral
scenario_kinds: [interview]
answer:
  target_sec: 60
  tone: honest
tags: [failure, incident, honesty]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-25T10:12:00+08:00
  review_run: run-20261025-02
freshness:
  valid_from: null
  valid_until: null
  review_after: 2027-04-30
confidence:
  level: red
  reasons: [open_conflict, ref_yellow]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence_refs:
  - story:ledger-migration-2025
  - claim:ledger-migration-led
conflicts: ["cfl-01JCF8Q4R6T2W8Y4B6D2F8H1K3"]
conflict_state: none
card:
  l1: ["2025 对账 P1", "补偿任务漏退款", "我牵头复盘", "补了检查清单"]
  l2:
    - "2025-09 迁移当晚 P1，延迟 4 小时 12 分"
    - "根因是补偿任务漏了退款流水，不是架构问题"
    - "我牵头复盘，补了发布检查清单"
    - "之后对账 P95 从 45 分钟降到 8 分钟"
  fallback: "这次事故我有责任，具体数字我按复盘口径说，不粉饰。"
  evidence_refs:
    - story:ledger-migration-2025
    - claim:ledger-migration-led
  confidence:
    level: red
    reasons: [open_conflict, ref_yellow]
    rule: rule_v1
    computed_at: 2026-10-25T10:20:00+08:00
  built_from:
    - {id: "story:ledger-migration-2025", revision: 1}
    - {id: "claim:ledger-migration-led", revision: 3}
  do_not_say: ["零故障", "从没出过问题"]
---

# 你最大的失败是什么

## 一句话回答

2025 年 9 月账务迁移当晚，我负责的平台出了一个 P1：对账延迟 4 小时 12 分。责任在我——发布检查清单漏了一项。

## 展开

事故从 22:10 开始，到凌晨 02:05 追平，持续 3 小时 55 分。根因不是架构，是双写补偿任务没有覆盖退款流水，退款没有及时入账。我牵头复盘，把"补偿任务覆盖所有流水类型"补进了发布检查清单。之后对账 P95 从 45 分钟降到 8 分钟，这是迁移本身带来的改善。

我不会把这件事说成"很快就恢复了"：四个多小时的延迟对商户结算是实打实的影响，该认就认。

## 证据

<!-- 由编译器从 evidence_refs 解析生成，人工勿改 -->
- E1 · [[story:ledger-migration-2025]] · [[source:postmortem-2025]] · b-0001：「2025-09-18 22:10 至 2025-09-19 02:05，账务平台对账延迟，持续 3 小时 55 分，定级 P1」
- E2 · [[story:ledger-migration-2025]] · [[source:postmortem-2025]] · b-0002：「对账延迟峰值 4 小时 12 分」
- E3 · [[story:ledger-migration-2025]] · [[source:postmortem-2025]] · b-0003：「根因：分库迁移中新旧双写补偿任务未覆盖退款流水」
- E4 · [[claim:ledger-migration-led]] · [[source:resume-2026]] · b-0004：「主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易」

## 边界与不知道

- 年度可用性的最终口径还在和监控核对，面试只说复盘口径 99.95%。
- 我不确定当时是否还有别的补偿任务缺口，复盘只覆盖了发现的这一类。
- 简历里"迁移全程无异常"的表述已被复盘推翻，现场不要再用。

## 追问预案

- 问：为什么没发现补偿任务漏了退款流水？ → 答：检查清单按服务拆，退款流水这一类没人认领，这是我的漏洞。
- 问：你从中改了什么？ → 答：把"补偿任务覆盖所有流水类型"做成上线前强制校验，已写进模板。
- 问：如果重来你会怎么避免？ → 答：上线前用流水类型清单逐项打勾，而不是靠人记得。
