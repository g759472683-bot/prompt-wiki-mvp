---
schema_version: "1.0"
id: source:{{slug}}
type: source
title: "{{文件名或文档标题}}"
summary: "{{这份文档是什么，一句话}}"
status: active
language: zh-CN
revision: 1
created_at: "{{2026-10-25T10:00:00+08:00}}"
updated_at: "{{2026-10-25T10:00:00+08:00}}"
created_by: compiler
run_id: "{{run-20261025-01}}"
source:
  doc_id: "{{doc-xxx}}"
  filename: "{{原始文件名.pdf}}"
  mime: "{{application/pdf}}"
  sha256: "{{64 位十六进制}}"
  bytes: 0
  pages: 1
  imported_at: "{{2026-10-25T10:00:00+08:00}}"
  parser: "{{pdfplumber}}"
  parser_version: "{{0.11.4}}"
  language: "zh-CN"
trust: medium                 # high | medium | low；low 不得单独支撑页面
version: 1
supersedes: null
archived_at: null
extraction:
  blocks: 1
  warnings: []
  coverage: full              # full | partial
  ocr: false
notes: null
---

# {{标题}}

<!-- 正文 block 由解析器生成，禁止人工编辑。
     每个 block 以 HTML 注释标注 id / 页码 / 字符偏移，quote 必须逐字来自 block 文本。 -->

<!-- b-0001 | p.1 | chars:0-120 -->
{{第一段原文，保持原样，不要改写、不要翻译、不要合并段落。}}

<!-- b-0002 | p.1 | chars:121-260 -->
{{第二段原文。}}

## 导入备注（人工可写）

- {{解析警告、需要人工核对的地方、来源可信度判断}}
