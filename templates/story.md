---
schema_version: "1.0"
id: story:{{slug}}
type: story
title: "{{案例标题}}"
summary: "{{什么场景、我做了什么、结果如何，一句话}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
story_kind: project             # project | incident | conflict | achievement
role: "{{技术负责人}}"
period: "{{2025-03 ~ 2025-09}}"
team_size: 8
stack: ["{{MySQL}}", "{{Kafka}}"]
metrics: ["metric:{{slug}}"]
tags: ["{{tag}}"]
review:
  reviewed_by: "human:{{name}}"
  reviewed_at: "{{2026-10-25T10:00:00+08:00}}"
  review_run: null
freshness:
  valid_from: null
  valid_until: null
  review_after: "{{2027-04-30}}"
confidence:
  level: yellow
  reasons: [disputed_evidence]
  rule: rule_v1
  computed_at: "{{2026-10-25T10:00:00+08:00}}"
evidence:
  - source: source:{{source-slug}}
    source_version: 1
    block: b-0001
    quote: "{{逐字引用}}"
    role: primary
    verified: true
conflicts: []
conflict_state: none
---

# {{案例标题}}

## 情境 S

{{当时什么局面、多大规模、为什么难。2-4 句，含数字（E1）。}}

## 任务 T

{{我具体负责什么、目标是什么、不能失败的是什么。}}

## 行动 A

1. {{关键决策 1，以及为什么这么选}}
2. {{关键决策 2}}
3. {{我个人的动作，不是团队的泛泛描述}}

## 结果 R

{{可验证结果（E2）；如果有失败或代价，如实写。不要用"圆满成功"。}}

## 复盘与边界

- {{如果重来会改什么}}
- {{这个经验不适用于什么场景}}

## 追问预案

- 问：{{最可能的追问}} → 答：{{一句话}}
- 问：{{最尖锐的追问}} → 答：{{一句话}}

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:{{source-slug}}]] · b-0001：「{{quote}}」
