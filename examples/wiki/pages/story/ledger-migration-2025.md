---
schema_version: "1.0"
id: story:ledger-migration-2025
type: story
title: "账务平台分库迁移与那晚的 P1"
summary: "12 个服务、日均 2.3 亿笔的分库迁移，当晚对账 P1，复盘与代价"
status: active
language: zh-CN
revision: 1
created_at: 2026-10-25T10:04:00+08:00
updated_at: 2026-10-25T10:12:00+08:00
created_by: compiler
run_id: run-20261025-02
story_kind: incident
role: "技术负责人"
period: "2025-03 ~ 2025-10"
team_size: 8
stack: ["MySQL", "Kafka", "Redis"]
metrics: ["metric:availability-2025"]
tags: [migration, incident, payment]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-25T10:12:00+08:00
  review_run: run-20261025-02
freshness:
  valid_from: null
  valid_until: null
  review_after: 2027-04-30
confidence:
  level: yellow
  reasons: [disputed_evidence]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0004
    quote: "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易"
    role: primary
    verified: true
  - source: source:resume-2026
    source_version: 1
    block: b-0005
    quote: "对账延迟 P95 从 45 分钟降至 8 分钟"
    role: supporting
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0001
    quote: "2025-09-18 22:10 至 2025-09-19 02:05，账务平台对账延迟，持续 3 小时 55 分，定级 P1"
    role: primary
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0002
    quote: "对账延迟峰值 4 小时 12 分"
    role: supporting
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0003
    quote: "根因：分库迁移中新旧双写补偿任务未覆盖退款流水"
    role: supporting
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0004
    quote: "22:40 回滚补偿任务并手工对账，02:05 全部追平"
    role: supporting
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0005
    quote: '复盘结论：迁移由林舟牵头，架构方案无问题；发布检查清单缺少"补偿任务覆盖退款流水"一项，已补充。'
    role: supporting
    verified: true
  - source: source:postmortem-2025
    source_version: 1
    block: b-0006
    quote: "2025 年度可用性 99.95%"
    role: counter
    verified: true
conflicts: ["cfl-01JCF7P3T2M8N4R6W9Y1B5D7F3"]
conflict_state: none
---

# 账务平台分库迁移与那晚的 P1

## 情境 S

2025 年账务平台单库接近容量上限，12 个服务、日均 2.3 亿笔交易必须迁移到分库分表架构（E1）。迁移窗口放在夜间，但不能停交易。

## 任务 T

我牵头方案与推进：按商户 ID 分片、双写 6 周、灰度放量（E1）。目标有两个：迁移期间交易不中断；对账数据不能乱。

## 行动 A

1. 选商户 ID 作为分片键，保证同一商户的账务在一个分片内，减少跨分片事务。
2. 双写 6 周，用对账任务校验新旧库一致性，再灰度放量。
3. 发布检查清单按服务拆分，每个服务负责人签字。

## 结果 R

迁移整体按时完成，对账延迟 P95 从 45 分钟降到 8 分钟（E2）。但 2025-09-18 当晚发生了 P1：对账延迟持续 3 小时 55 分、峰值 4 小时 12 分（E3、E4）。根因是双写补偿任务没有覆盖退款流水（E5），22:40 回滚补偿任务并手工对账，02:05 全部追平（E6）。

代价是真实的：2025 年度可用性只有 99.95%，没有达到 99.99% 的目标（E7）。简历里"迁移全程无异常"的表述已被复盘推翻，不能再用。

## 复盘与边界

- 我个人的责任：发布检查清单漏了"补偿任务覆盖退款流水"这一项，已补充到清单模板（E8）。
- 如果重来：会把"补偿任务覆盖所有流水类型"做成上线前的强制校验，而不是靠人记得。
- 这个案例适合回答"最大失败""怎么处理线上事故""迁移怎么做"，不适合用来证明"我能保证不出问题"。

## 追问预案

- 问：这事到底怪谁？ → 答：我是负责人，清单是我定的，责任在我；根因是流程缺口，不是某个执行同学。
- 问：那你凭什么说迁移成功？ → 答：迁移目标和对账延迟改善是事实，P1 也是事实，两件事都要说。

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:resume-2026]] · b-0004：「主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔交易」
- E2 · [[source:resume-2026]] · b-0005：「对账延迟 P95 从 45 分钟降至 8 分钟」
- E3 · [[source:postmortem-2025]] · b-0001：「2025-09-18 22:10 至 2025-09-19 02:05，账务平台对账延迟，持续 3 小时 55 分，定级 P1」
- E4 · [[source:postmortem-2025]] · b-0002：「对账延迟峰值 4 小时 12 分」
- E5 · [[source:postmortem-2025]] · b-0003：「根因：分库迁移中新旧双写补偿任务未覆盖退款流水」
- E6 · [[source:postmortem-2025]] · b-0004：「22:40 回滚补偿任务并手工对账，02:05 全部追平」
- E7 · [[source:postmortem-2025]] · b-0006：「2025 年度可用性 99.95%」
- E8 · [[source:postmortem-2025]] · b-0005：「架构方案无问题；发布检查清单缺少」
