---
schema_version: "1.0"
id: scenario:{{slug}}
type: scenario
title: "{{公司/对象}} · {{场景类型}}"
summary: "{{时间、对象、目标，一句话}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
scenario_kind: interview        # interview | pitch | meeting
counterparty: entity:{{org-slug}}
scheduled_at: "{{2026-11-03T14:00:00+08:00}}"
duration_min: 60
goal: "{{拿到后端负责人 offer，重点证明高并发交易与团队管理}}"
audience: ["{{CTO 陈默}}", "{{HRBP 周岚}}"]
questions:
  - {qa: "qa:{{slug-1}}", priority: 1, must_hit: true, note: "{{为什么必问}}"}
  - {qa: "qa:{{slug-2}}", priority: 1, must_hit: true}
  - {qa: "qa:{{slug-3}}", priority: 2, must_hit: false}
constraints:
  do_not_claim:
    - "{{不要承诺 3 个月内重构实时链路}}"
    - "{{不要使用'零故障'这类绝对化表述}}"
  must_mention:
    - "{{团队管理规模}}"
prepared_at: null
prep_run: null
tags: ["interview", "{{company}}"]
---

# {{公司}} · {{场景类型}}

## 会前简报

{{对方是谁、业务阶段、这次见谁、对方最在意什么。3-5 句。}}

## 对方关注点

- {{关注点 1，对应哪张卡}}
- {{关注点 2}}

## 我的三个目标

1. {{必须拿下的印象}}
2. {{必须问清的信息}}
3. {{必须避免的坑}}

## 风险与禁区

- {{哪个问题我证据最弱，准备用兜底}}
- {{哪些话不能说（与 constraints 对应）}}

## 问题清单

| 优先级 | 问题 | 卡片 | 必答 | 备注 |
|---|---|---|---|---|
| 1 | [[qa:{{slug-1}}|{{问题}}]] | ✅ | 是 | {{备注}} |
| 1 | [[qa:{{slug-2}}|{{问题}}]] | ✅ | 是 | |
| 2 | [[qa:{{slug-3}}|{{问题}}]] | ✅ | 否 | |
