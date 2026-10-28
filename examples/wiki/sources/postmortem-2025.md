---
schema_version: "1.0"
id: source:postmortem-2025
type: source
title: "账务平台 2025-09-18 对账延迟 P1 复盘"
summary: "一次 P1 事故的时间线、根因、处置与年度可用性口径"
status: active
language: zh-CN
revision: 1
created_at: 2026-10-25T10:02:00+08:00
updated_at: 2026-10-25T10:02:00+08:00
created_by: compiler
run_id: run-20261025-02
source:
  doc_id: doc-postmortem-2025
  filename: "账务平台-20250918-P1-复盘.docx"
  mime: application/vnd.openxmlformats-officedocument.wordprocessingml.document
  sha256: "b2c3d4e5f6071829b2c3d4e5f6071829b2c3d4e5f6071829b2c3d4e5f6071829"
  bytes: 96256
  pages: 3
  imported_at: 2026-10-25T10:02:00+08:00
  parser: docx2txt
  parser_version: "0.8"
  language: zh-CN
trust: high
version: 1
supersedes: null
archived_at: null
extraction:
  blocks: 6
  warnings:
    - code: TABLE_FLATTENED
      block: b-0002
      message: "时间线表格按纯文本重建，数值已人工核对"
  coverage: full
  ocr: false
notes: "复盘由我本人撰写，数据来自监控与财务对账记录。"
tags: [postmortem, incident, ledger]
---

# 账务平台 2025-09-18 对账延迟 P1 复盘

<!-- b-0001 | p.1 | chars:0-58 -->
2025-09-18 22:10 至 2025-09-19 02:05，账务平台对账延迟，持续 3 小时 55 分，定级 P1。

<!-- b-0002 | p.1 | chars:59-125 -->
影响：对账延迟峰值 4 小时 12 分，涉及 3 个商户的批量结算，未影响资金安全。

<!-- b-0003 | p.1 | chars:126-188 -->
根因：分库迁移中新旧双写补偿任务未覆盖退款流水，导致退款流水未及时入账。

<!-- b-0004 | p.2 | chars:0-45 -->
处置：22:40 回滚补偿任务并手工对账，02:05 全部追平。

<!-- b-0005 | p.2 | chars:46-118 -->
复盘结论：迁移由林舟牵头，架构方案无问题；发布检查清单缺少"补偿任务覆盖退款流水"一项，已补充。

<!-- b-0006 | p.3 | chars:0-44 -->
2025 年度可用性 99.95%，未达 99.99% 目标。
