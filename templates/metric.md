---
schema_version: "1.0"
id: metric:{{slug}}
type: metric
title: "{{指标名}}"
summary: "{{值 + 口径，一句话}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
metric:
  name: "{{账务平台年度可用性}}"
  key: "{{availability}}"       # 全局唯一，冲突检测按它聚合
  value: "{{99.95%}}"
  value_num: 99.95
  unit: "%"
  direction: higher             # higher | lower
  period: "{{2025}}"
  method: "{{按分钟不可用时长 / 全年分钟数}}"
  scope: "{{星桥支付账务平台}}"
tags: ["{{tag}}"]
review:
  reviewed_by: "human:{{name}}"
  reviewed_at: "{{2026-10-25T10:00:00+08:00}}"
  review_run: null
freshness:
  valid_from: "{{2025-01-01}}"
  valid_until: "{{2026-12-31}}"
  review_after: "{{2026-11-30}}"
confidence:
  level: red
  reasons: [open_conflict]
  rule: rule_v1
  computed_at: "{{2026-10-25T10:00:00+08:00}}"
evidence:
  - source: source:{{source-slug}}
    source_version: 1
    block: b-0001
    quote: "{{含该数字的逐字原文}}"
    role: primary
    verified: true
conflicts: ["{{cfl-...}}"]
conflict_state: open
---

# {{指标名}}

## 口径

{{这个数字到底统计什么、不统计什么。必须能回答"怎么算的"。}}

## 计算方式

{{公式或分母分子；采样周期；剔除规则。}}

## 为什么可信

- 来源：[[source:{{source-slug}}]]（{{trust}}）
- {{是否有第二来源交叉验证；若有冲突，写在这里}}

## 常见追问

- 问：这个数怎么算的？ → 答：{{一句话}}
- 问：为什么和别人说的不一样？ → 答：{{口径差异，或承认冲突未决}}

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:{{source-slug}}]] · b-0001：「{{quote}}」
