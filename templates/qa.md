---
schema_version: "1.0"
id: qa:{{slug}}
type: qa
title: "{{问题短标题}}"
summary: "{{一句话答案方向}}"
status: draft
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
question: "{{规范问句，≤40 字}}"
question_variants:
  - "{{口语问法 1}}"
  - "{{ASR 可能听到的问法 2}}"
  - "{{更尖锐的问法 3}}"
intent: behavioral              # factual | behavioral | technical | motivation | risk | commercial | hr | other
scenario_kinds: [interview]     # interview | pitch | meeting
answer:
  target_sec: 60                # 30 | 60 | 90
  tone: honest                  # confident | honest | concise
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
  reasons: [single_source, unreviewed]
  rule: rule_v1
  computed_at: "{{2026-10-25T10:00:00+08:00}}"
evidence_refs:
  - claim:{{claim-slug}}
  - story:{{story-slug}}
conflicts: []
conflict_state: none
card:
  l1: ["{{关键词1}}", "{{关键词2}}", "{{关键词3}}"]
  l2:
    - "{{开口句：先给结论，不要背景}}"
    - "{{论据 1，带一个可追溯的数字}}"
    - "{{论据 2}}"
    - "{{收尾：拉回岗位/对方关注点}}"
  fallback: "{{兜底：诚实 + 具体 + 不承诺不知道的事，≤100 字}}"
  evidence_refs:
    - claim:{{claim-slug}}
    - story:{{story-slug}}
  confidence:
    level: yellow
    reasons: [single_source, unreviewed]
    rule: rule_v1
    computed_at: "{{2026-10-25T10:00:00+08:00}}"
  built_from:
    - {id: "claim:{{claim-slug}}", revision: 1}
    - {id: "story:{{story-slug}}", revision: 1}
  do_not_say: ["{{绝对化表述}}"]
---

# {{问题短标题}}

## 一句话回答

{{30 秒版结论，1-2 句，含最关键的支撑事实（E1）。}}

## 展开

{{60/90 秒版：先结论，再 2 个论据，最后拉回对方关注点。每个数字标 E 编号。}}

## 证据

<!-- 由编译器从 evidence_refs 解析生成，人工勿改 -->
- E1 · [[claim:{{claim-slug}}]] · [[source:{{source-slug}}]] · b-0001：「{{quote}}」

## 边界与不知道

- {{我确实不确定的部分，以及会怎么补}}
- {{不能承诺的事}}

## 追问预案

- 问：{{追问 1}} → 答：{{一句话}}
- 问：{{追问 2}} → 答：{{一句话，必要时用兜底}}
