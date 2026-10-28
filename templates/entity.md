---
schema_version: "1.0"
id: entity:{{slug}}
type: entity
title: "{{实体名称}}"
summary: "{{一句话定位，如：企业级数据平台服务商，2024 年营收 6.8 亿元}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
entity_kind: org                # person | org | product | project | concept
aliases: ["{{别名}}", "{{English Name}}"]
tags: ["{{tag}}"]
review:
  reviewed_by: "human:{{name}}"
  reviewed_at: "{{2026-10-25T10:00:00+08:00}}"
  review_run: "{{run-20261025-01}}"
freshness:
  valid_from: null
  valid_until: null
  review_after: "{{2027-04-30}}"
confidence:
  level: yellow
  reasons: [single_source, review_due]
  rule: rule_v1
  computed_at: "{{2026-10-25T10:00:00+08:00}}"
evidence:
  - source: source:{{source-slug}}
    source_version: 1
    block: b-0001
    quote: "{{逐字引用，20-120 字}}"
    role: primary
    verified: true
conflicts: []
conflict_state: none
---

# {{实体名称}}

## 一句话定义

{{它是什么，为什么与我的叙事相关。1-2 句。}}

## 关键事实

- {{事实 1（E1）}}
- {{事实 2（E1）}}

## 与我的关系

{{我为什么关注它：面试目标公司 / 前雇主 / 项目载体。}}

## 关联页面

- [[scenario:{{slug}}|{{场景}}]]
- [[qa:{{slug}}|{{问题}}]]

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:{{source-slug}}]] · b-0001：「{{quote}}」
