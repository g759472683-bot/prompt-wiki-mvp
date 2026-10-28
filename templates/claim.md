---
schema_version: "1.0"
id: claim:{{slug}}
type: claim
title: "{{断言的短标题}}"
summary: "{{一句话说清这条断言，用于索引与检索}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
statement: "{{一句可判真假的陈述，≤60 字}}"
claim_kind: experience          # experience | capability | technical | commercial | customer | market
scope: "{{适用于回答什么；不适用于证明什么。必须写'不适用'}}"
verification: verified          # verified | unverified
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
  reasons: [single_source]
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

# {{标题}}

## 一句话说法

{{把 statement 用人话说一遍，带一句"所以我能说……"}}

## 成立条件

- {{需要什么前提才成立}}
- {{不适用于什么场景，避免过度外推}}

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:{{source-slug}}]] · b-0001：「{{quote}}」

## 可能的反驳

- {{对方可能怎么质疑（E2）}}
- {{我的回应边界：哪些我承认不知道}}
