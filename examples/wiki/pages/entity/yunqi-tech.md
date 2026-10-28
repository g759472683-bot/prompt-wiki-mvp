---
schema_version: "1.0"
id: entity:yunqi-tech
type: entity
title: "云栖科技"
summary: "企业级数据平台服务商，目标岗位所在公司，2024 年营收 6.8 亿元"
status: active
language: zh-CN
revision: 1
created_at: 2026-10-20T09:25:00+08:00
updated_at: 2026-10-20T09:25:00+08:00
created_by: compiler
run_id: run-20261020-01
entity_kind: org
aliases: ["云栖", "Yunqi Tech"]
tags: [company, target]
review:
  reviewed_by: human:lin
  reviewed_at: 2026-10-21T20:10:00+08:00
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
  - source: source:jd-yunqi-2026
    source_version: 1
    block: b-0001
    quote: "企业级数据平台服务商，2024 年营收 6.8 亿元"
    role: primary
    verified: true
  - source: source:jd-yunqi-2026
    source_version: 1
    block: b-0002
    quote: "管理 12 人团队，负责实时数据链路"
    role: primary
    verified: true
  - source: source:jd-yunqi-2026
    source_version: 1
    block: b-0004
    quote: "2026 年把核心链路 P99 延迟压到 200ms 以内"
    role: supporting
    verified: true
conflicts: []
conflict_state: none
---

# 云栖科技

## 一句话定义

云栖科技是一家企业级数据平台服务商，2024 年营收 6.8 亿元、员工约 700 人（E1）；这个岗位要补的是实时数据链路的负责人（E2）。

## 关键事实

- 业务：企业级数据平台，营收 6.8 亿元，员工约 700 人（E1）。
- 岗位：后端负责人，汇报 CTO，管理 12 人团队，负责实时数据链路（E2）。
- 2026 年的硬目标：核心链路 P99 压到 200ms 以内（E3）。

## 与我的关系

这是我的目标公司。我的支付账务背景能对上它的高并发一致性要求，但实时数据链路是我需要补的叙事（见 [[qa:why-this-role|为什么选择云栖]]）。

## 关联页面

- [[scenario:yunqi-backend-lead|云栖科技 · 后端负责人面试]]
- [[qa:why-this-role|为什么选择云栖科技]]

## 证据

<!-- 由编译器从 frontmatter 生成，人工勿改 -->
- E1 · [[source:jd-yunqi-2026]] · b-0001：「企业级数据平台服务商，2024 年营收 6.8 亿元」
- E2 · [[source:jd-yunqi-2026]] · b-0002：「管理 12 人团队，负责实时数据链路」
- E3 · [[source:jd-yunqi-2026]] · b-0004：「2026 年把核心链路 P99 延迟压到 200ms 以内」
