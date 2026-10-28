# 技术方案与 API v0.1（L3）

> 配套：[PRD v0.1](prd-v0.1-l3.md) · [Wiki Schema v1.0](wiki-schema-contract-v1.0.md)
> 目标：**会前编译、会中只读、会后回写**。运行时热路径不查 Wiki、不调 LLM。

---

## 1. 七条架构原则

1. **Wiki 是源数据库，卡包是物化视图。** 页面/证据/冲突/Pin 是内部实现；App 只消费 `pack.json`。
2. **编译期做重活，运行期只读。** L1/L2 在会前生成；现场匹配在内存里做。
3. **客户端优先。** 已预载卡包时，命中、渲染、引用全部本地完成；服务端只做兜底与同步。
4. **证据不可绕过。** 卡片里的每个数字/断言必须有 citation；解析失败就降级，不静默删。
5. **冲突显式化。** 红卡先兜底；不允许"看起来自信"。
6. **人工权威。** 用户改过的句子写成 Pin，重编译逐条校验。
7. **单用户、单机可跑。** MVP 用 SQLite + 文件 + 一个 worker；不引入 Postgres/K8s/向量库。

---

## 2. 系统图

```text
┌────────────── Android (Kotlin/Compose) ──────────────┐
│ 今日 / 卡包 / 现场 / 复盘                              │
│ 本地：pack 缓存 · 匹配器 · 引用弹层 · 反馈 outbox        │
│ 服务：前台录音 · ASR WebSocket · 蓝牙媒体键 · 常亮        │
└───────────────┬──────────────────────────────────────┘
                │ HTTPS / SSE / WS
┌───────────────▼────────────── FastAPI ───────────────┐
│ auth · documents · scenarios · jobs · packs · ask     │
│ sessions · feedback · sources · admin(内部)            │
│                                                       │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐   │
│  │ Ingest   │  │ Compiler  │  │ Card Builder     │   │
│  │ parse    │→ │ pages/ops │→ │ 20 卡 + L1/L2    │   │
│  │ blocks   │  │ staging   │  │ 引用/置信度       │   │
│  └──────────┘  └───────────┘  └──────────────────┘   │
│         │             │                │              │
│         ▼             ▼                ▼              │
│   data/wiki/     data/staging/    data/packs/         │
│   SQLite: docs/jobs/packs/sessions/feedback/fts5      │
└───────────────────────────────────────────────────────┘
                │
        LLM provider（仅编译/兜底，服务端密钥）
```

---

## 3. 数据布局

```text
data/
├── app.db                       # SQLite WAL：users/documents/jobs/packs/sessions/feedback
├── users/<uid>/
│   ├── wiki/                    # 与契约 §3 完全一致（内部）
│   │   ├── index.md
│   │   ├── pages/{claim,story,metric,qa,entity,scenario}/
│   │   ├── sources/
│   │   ├── pins/
│   │   ├── conflicts/
│   │   └── runs/
│   ├── packs/<pack_id>.json     # 物化卡包（不可变快照）
│   ├── sessions/<session_id>.jsonl
│   └── uploads/<document_id>.<ext>
└── backups/
```

- Markdown + YAML 仍是唯一事实源；SQLite 可重建。
- `packs/*.json` 是**发布产物**，由已审核卡片组装，带版本与 etag。
- Session 只存元数据 + 事件；转写默认不落盘（用户开启才存）。

---

## 4. 编译与出包流水线

```text
上传 → 解析(block) → 建 source 页 → 页面编译(CREATE/UPDATE/LINK/CONFLICT)
     → 预测 20 问 → 逐题生成 qa 卡(L1/L2/L3/兜底/引用/置信度)
     → 校验(断链/证据/数字/Pin/Lint) → 内部审核台
     → 人工批准 → 组装 pack vN → App 预载
```

### 4.1 阶段与预算

| 阶段 | 产出 | 预算 | 失败处理 |
|---|---|---|---|
| Parse | source.md + blocks + sha256 | ≤3s/10 页 | 拒绝并提示换格式 |
| Page compile | claim/story/metric/qa 草稿 | ≤20 ops/文档 | 重试 1 次 → 人工 |
| Card build | 20 张卡（含 3 层） | 20 张 ≤4 min p50 | 单卡失败不阻塞整包 |
| Validate | 校验报告 | ≤1s | blocker 卡不发布 |
| Review | 批准/编辑/排除 | 人工 | 超时 48h 提醒 |
| Publish | pack.json + etag | ≤1s | 保留上一版 |

### 4.2 卡片生成策略

- 预测问题来源：JD/BP/岗位模板 + 简历/项目页 + 历史复盘（第二轮起）。
- 每题一个 `qa` 页；`card.l1/l2` 编译期写死；`l3` 是 qa 正文。
- 20 张的配额建议：`must_hit 8 + 高频 8 + 风险/追问 4`。
- 每张卡必须有 `evidence_refs` 与 `citations`；无引用则不允许绿色。
- 红卡允许进包，但必须带 `fallback` 与原因，且 App 强制确认。
- 用户"这题没用"→ 记排除；下一版不再生成（可撤销）。

### 4.3 页面编译与 Pin

完全复用 [契约 §9–§11](wiki-schema-contract-v1.0.md)：

- `base_revision` 乐观锁；冲突不裁决；Pin 逐条校验。
- 用户改卡 → 写对应页面字段的 Pin（`origin: card_edit`），不是直接改 pack。
- 重编译后先跑 Pin ledger，再重新组装 pack；有孤儿 Pin 则阻止该卡发布。
- Pack 里记录 `pinned_fields`，UI 显示"已钉住"。

### 4.4 Pack 版本与失效

- 每次发布 `version += 1`，内容哈希作 `etag`。
- 触发重建：文档变更、用户排除/新增问题、冲突裁决、Pin 变更、每 30 天。
- App 打开时校验 `etag`；过期显示"有 2 张卡需要更新"，但**不阻塞现场**（用旧版）。

---

## 5. 运行时时序

### 5.1 预载（会前）

```text
App: GET /v1/packs/{id} (If-None-Match)
→ 校验 etag / schema_version
→ 解压到内存 + 落盘缓存
→ 预解析 citations（quote/来源/页码）
→ 标记"离线可用"
```

### 5.2 现场触发

```text
[按下按钮 / 蓝牙媒体键]
  → 震动 + 视觉反馈（≤100ms）
  → 读取最近 15s 转写缓冲（partial + final）
  → 规范化（标点/语气词/数字/英文小写）
  → 内存匹配 20 张卡：
       1) variant 完全一致
       2) token 重合度
       3) 场景优先级
       4) 冲突扣分
  → 命中：立即渲染 L1 → L2 → L3(点击)
  → 未命中：本地 BM25（citation 片段）→ 仍无 → 兜底卡
  → 需要"现场组装"时：POST /v1/ask（SSE），L1 不等它
```

**关键**：L1 永远不被网络阻塞。`/v1/ask` 只用于未命中/兜底；它的 `l1` 帧也不覆盖本地已有结果。

### 5.3 匹配算法（客户端）

```text
score = 4.0*exact_variant
      + 2.0*token_jaccard
      + 0.5*priority_boost
      - 3.0*open_conflict
accept if score >= 3.2
```

- 20 张卡时，纯 Kotlin 计算 <5ms；不需要客户端 FTS5。
- 规范化与阈值先用契约 §13.2 的初始值，W5 用真实 ASR 语料校准。
- 匹配失败但缓冲非空：显示最近 5 个问题快选（长按卡包列表）。

### 5.4 降级

| 情况 | 行为 |
|---|---|
| 缓冲滞后 >1.5s | 显示"还在听" + 快选 |
| 无命中 | 兜底话术 + 2 条最相关原话（本地） |
| 引用解析失败 | 该条不展示；卡片降红；兜底置顶 |
| 断网 | 已预载包完全可用；反馈排队 |
| 服务端 5xx | 不重试阻塞；用本地；后台补同步 |
| Pack 过期 | 横幅提示；继续用旧版 |
| ASR 断开 | 转文字输入；卡包照常 |

---

## 6. 时延预算

### 6.1 本地命中（主路径）

| 步骤 | P50 | P95 |
|---|---:|---:|
| 按键事件 → 反馈 | 20ms | 60ms |
| 读缓冲 + 规范化 | 8ms | 20ms |
| 匹配 20 张 | 3ms | 8ms |
| L1 渲染 | 30ms | 80ms |
| L2 渲染 | +30ms | +80ms |
| L3（本地正文） | +20ms | +60ms |
| **L1 合计（按下起）** | **~60ms** | **~170ms** |
| **L2 合计** | **~90ms** | **~250ms** |

> ASR 的 final 延迟不计入"按下→L1"，但影响匹配率；W5 单独测 `question_end → buffer_final`。

### 6.2 服务端兜底（仅未命中）

| 步骤 | P50 | P95 |
|---|---:|---:|
| 建连 + 请求 | 150ms | 400ms |
| BM25 检索 | 30ms | 80ms |
| LLM 单轮组装 | 700ms | 1500ms |
| **合计** | **~900ms** | **~2s** |

兜底路径不阻塞 L1；L1 先用本地兜底卡占位。

---

## 7. API v0.1

Base：`https://api.example.com/v1` · JSON · `Authorization: Bearer <token>`
错误：`{ "error": { "code": "...", "message": "...", "trace_id": "..." } }`
幂等：`POST` 支持 `Idempotency-Key`（prep/ask/feedback 必带）。

### 7.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/device` | `{device_id, invite_code, name?}` → `{token, user_id, expires_at}` |

### 7.2 文档

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/documents` | multipart `file` + `doc_type` → `{document_id, status}` |
| GET | `/documents/{id}` | `{status, source_id, blocks, warnings}` |
| DELETE | `/documents/{id}` | 软删 7 天后物理删 |
| POST | `/documents/{id}/compile` | 同步调试入口；产品走 `/compile-jobs` |
| POST | `/compile-jobs` | 入队异步编译：`{document_id, with_cards}` → 202 job |
| GET | `/jobs` | 我的 job 列表 |
| GET | `/runs/{run_id}/review` | staging 审核视图（页面/卡片/collision/warnings） |
| POST | `/runs/{run_id}/approve` | 批准：页面写正式 Wiki，pack 写 `packs/`（已存在则 409） |

### 7.3 场景与准备

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/scenarios` | `{kind,title,counterparty,scheduled_at,goal,document_ids}` |
| GET | `/scenarios` | 列表（首页） |
| GET | `/scenarios/{id}` | 详情 + 最新 pack 摘要 |
| POST | `/scenarios/{id}/prep` | `{document_ids?, regenerate?}` → `{job_id}` |
| GET | `/jobs/{id}` | `{status,progress,result,error}` |

> D5 已实现异步编译与审核/发布：`POST /compile-jobs` 入队，`python -m app.worker` 单 worker 执行，`GET /runs/{id}/review` 审核，`POST /runs/{id}/approve` 发布。`/documents/{id}/compile` 仅保留为同步调试。场景 `prep` 仍是 D6。

`job.status`：`queued / running / succeeded / failed`。

### 7.4 卡包与卡片

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/packs/{id}` | 完整 pack（`ETag` 头） |
| POST | `/packs/{id}/approve` | 发布：`{version, etag}` |
| PATCH | `/cards/{card_id}` | 改 L1/L2/兜底/禁用词 → 生成 Pin |
| POST | `/cards/{card_id}/decision` | `{action: keep|exclude|needs_fix, note?}` |
| GET | `/sources/{source_id}/blocks/{block_id}` | 引用弹层：`{quote, before, after, page}` |

### 7.5 现场查询（SSE）

```http
POST /ask
{
  "scenario_id": "scenario:yunqi-backend-lead",
  "pack_id": "pack-01J...",
  "question": "你最大的失败是什么",
  "trigger": "manual",
  "client_ts": "2026-11-03T14:12:03+08:00",
  "local_miss": false
}
```

事件：

```text
event: l1
data: {"card_id":"qa:biggest-failure","l1":[...],"confidence":{"level":"red"},"must_show_fallback_first":true}

event: l2
data: {"l2":[...]}

event: l3
data: {"l3_markdown":"...","citations":[...]}

event: done
data: {"ask_id":"ask-...","matched":{...},"timings_ms":{...},"notices":[...]}
```

- `local_miss=true` 时服务端走 BM25 + 单轮组装；仍无则 `l1` 返回兜底卡。
- `done` 帧结构沿用 [query-response.schema.json](../schema/query-response.schema.json)。

### 7.6 会话与反馈

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/sessions` | `{scenario_id, pack_id}` → `{session_id}` |
| POST | `/sessions/{id}/segments` | 批量 `{segments:[{start_ms,end_ms,text,is_final}]}` |
| POST | `/sessions/{id}/close` | 结束并生成复盘摘要 |
| GET | `/sessions/{id}/review` | 时间线 + 触发/采纳/兜底统计 + 待改进问题 |
| POST | `/feedback` | `{event, ask_id, card_id, at, latency_ms, meta}` |

`event` 枚举：`ask_shown / card_useful / card_useless / fallback_used / card_edited / prep_completed`。

### 7.7 内部

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/packs/{id}/review` | 卡片级 diff/依据/Pin 影响（Basic Auth + IP 白名单） |
| POST | `/admin/packs/{id}/approve` | 批量批准 |
| GET | `/healthz` | 存活 |

---

## 8. Pack JSON（App 契约）

```json
{
  "schema_version": "1.0",
  "pack_id": "pack-01JCFA2B4C6D8E0F2G4H6J8K0L",
  "scenario_id": "scenario:yunqi-backend-lead",
  "version": 3,
  "approved_at": "2026-10-25T10:12:00+08:00",
  "etag": "sha256:2f9c...",
  "cards": [
    {
      "qa_id": "qa:biggest-failure",
      "question": "你最大的失败是什么？",
      "variants": ["你最大的失败是什么", "说一个你搞砸的事"],
      "l1": ["2025 对账 P1", "补偿任务漏退款", "我牵头复盘"],
      "l2": ["2025-09 迁移当晚 P1，延迟 4 小时 12 分", "..."],
      "l3_markdown": "## 一句话回答 ...",
      "fallback": "这次事故我有责任，具体数字我按复盘口径说，不粉饰。",
      "confidence": {"level": "red", "reasons": ["open_conflict"]},
      "must_show_fallback_first": true,
      "citations": [
        {"source": "source:postmortem-2025", "source_version": 1,
         "block": "b-0002", "quote": "对账延迟峰值 4 小时 12 分",
         "page_label": "《P1 复盘》第 1 页", "supports": ["l2:0"]}
      ],
      "do_not_say": ["零故障"],
      "pinned_fields": ["card.l2[0]"]
    }
  ]
}
```

- 20 张卡约 40–80KB；一次预载。
- `l3_markdown` 里不出现 wiki 链接；引用只走 `citations`。
- `l1/l2` 直接渲染；`l3` 折叠。
- 卡顺序：`must_hit` → priority → confidence；红卡不隐藏但先兜底。

---

## 9. Android 实现要点

| 模块 | 方案 |
|---|---|
| UI | Jetpack Compose；四屏；深色高对比；字号可调 |
| 本地存储 | Room（pack/session/feedback outbox）+ EncryptedFile（敏感转写，可选） |
| 预载 | WorkManager 在 prep 完成后下载；校验 etag |
| 现场服务 | ForegroundService（type: microphone）+ 常亮 + 通知 |
| 权限 | RECORD_AUDIO、POST_NOTIFICATIONS、BLUETOOTH_CONNECT、FOREGROUND_SERVICE_MICROPHONE |
| ASR | AudioRecord 16k mono → WebSocket 流式；partial/final |
| 触发 | 屏幕大按钮；MediaSession + MediaButtonReceiver（播放/暂停）；音量键在 Activity 内兜底 |
| 锁屏 | **P0 不做锁屏可用**；要求解锁 + 常亮；P1 再评估 |
| 匹配 | 纯 Kotlin；20 张卡内存匹配；阈值可远程配置 |
| 引用 | 底部弹层；本地已有 quote/页码；点击不联网 |
| 离线 | pack + citations 全本地；反馈/事件队列 |
| 崩溃/保活 | 前台通知；被系统杀掉后回到现场页提示重启会话 |

**蓝牙兼容性**：不同耳机把按键映射为播放/暂停、接听/挂断或音量；W6 做 5 款机型 × 5 款耳机矩阵；不保证"任意耳机"，屏幕按钮始终可用。

---

## 10. 后端与部署

| 项 | MVP 选择 |
|---|---|
| 框架 | FastAPI + Uvicorn |
| DB | SQLite WAL（单机，≤50 用户） |
| 文件 | 本地磁盘 `data/` |
| 队列 | `jobs` 表 + 单 worker 进程（`python -m app.worker`，Compose 里的 `worker` 服务） |
| LLM | 服务端统一网关；超时/重试/成本上限 |
| 部署 | 1 台 2C4G VPS，Docker Compose，Caddy TLS |
| 备份 | 每日 tar（wiki/packs/db），保留 14 天 |
| 监控 | `/healthz` + 结构化日志 + 每日指标快照 |

**不做**：微服务、K8s、消息队列、向量库、多租户计费。3 人 8 周不需要。

---

## 11. 安全与隐私

- 传输 TLS；服务端密钥不落 App；用户数据按 uid 隔离。
- 上传文件只用于编译；删除账户 → 7 天内物理删除。
- 转写默认不落盘；开启后仅本人可见，可一键清除。
- 录音/转写状态常驻可见；不做"后台静默录音"。
- 文档视为不可信输入：编译 prompt 隔离，输出强校验，防提示注入。
- LLM 供应商选择"不用于训练"的企业条款；日志脱敏。
- 审核台 Basic Auth + IP 白名单；不暴露公网。

---

## 12. Build vs Reuse（W1 决策门）

| 方案 | 优点 | 风险 | 结论 |
|---|---|---|---|
| 自研薄编译器（Python） | 完全贴合契约/中文文档/Pin/冲突 | 2–3 周工作量 | **默认** |
| 包 llmwiki-compiler（MIT） | 已解决类型页/引用/review/lint | TypeScript 集成、中文 PDF 未验证、页面模型不同 | 备选：只做基线，不直接依赖 |
| 包 nashsu/llm_wiki | 产品完成度高 | 许可证 NOASSERTION、桌面应用难嵌入 | 不采用 |
| 包 kaas（Go, 无 embedding） | 方向一致 | 生态/文档少 | 观察 |

**决策规则**：W1 用 5 份真实文档跑自研 v0；若"20 张卡 ≥12 张能用"未达标，则改用 llmwiki-compiler 做编译后端，卡片层仍自研。**不要 fork 桌面应用。**

---

## 13. 测试与观测

### 13.1 测试

- **Golden set**：5 份文档 × 3 场景，60 个真实问句，人工标注"可接受/不可接受"。
- **契约测试**：pack/query/page schema 校验；证据 quote 逐字命中；数字可追溯。
- **时延**：真机 + 4G，冷/热启动，各 100 次；p50/p95。
- **引用审计**：每周 50 张卡，人工核对。
- **Pin 回归**：改 3 句 → 重编译 3 次 → 丢失 0。
- **断网/弱网**：飞行模式、200ms 丢包、ASR 断开。

### 13.2 埋点

`prep_started / pack_ready / card_edited / pack_opened / session_start / trigger / match_result / citation_open / feedback / session_end`

看板：L1/L2/L3 p95、命中率、兜底率、红卡占比、采纳率、编译成本/文档。

告警：L1 p95 >1.2s、错误率 >2%、prep 失败率 >5%。

---

## 14. 开工顺序（10 个工作日，先做 demo 不做 pilot）

| 天 | 交付 |
|---|---|
| D1 | 仓库骨架、CI、schema 校验、Docker Compose |
| D2 | 登录/邀请码、上传、解析、source block、文档列表 |
| D3–D4 | 页面编译 v0（claim/story/metric/qa）、证据校验、冲突记录 |
| D5–D6 | 20 卡生成、pack 组装、内部审核台（卡片级） |
| D7 | Android：登录、卡包下载、卡列表、现场静态页 |
| D8 | 本地匹配、触发、L1/L2、引用弹层 |
| D9 | 兜底/SSE、反馈、会话记录、离线缓存 |
| D10 | 端到端 demo + 5 份文档指标 + build/reuse 决策 |

**D10 门槛**：5 份真实文档 → 20 张卡 ≥16 能用；真机 L1 p95 ≤800ms；引用 100%；无 P0 崩溃。

---

## 15. 失败模式

| 失败 | 检测 | 处理 |
|---|---|---|
| 解析丢表格 | block 数异常/警告 | 提示换 PDF/人工补 |
| 卡片无依据 | 校验 blocker | 不发布；回退上一版 |
| 数字幻觉 | 数字追溯 | 该卡降红/删句 |
| Pin 孤儿 | ledger | 阻止该卡发布 |
| Pack 过期 | etag | 横幅提示；旧版可用 |
| ASR 断 | WS 心跳 | 转文字输入 |
| 服务被杀 | 前台通知 | 提示恢复会话 |
| 蓝牙无响应 | 按键超时 | 屏幕按钮 |
| LLM 超时 | 任务超时 | 重试/人工 |
| 成本超限 | 预算表 | 降级模型/暂停非关键卡 |

---

## 16. 与契约的对应关系

| 本文 | 契约 |
|---|---|
| 页面/证据/冲突/Pin | §6、§9–§11 |
| 卡片 L1/L2/L3 | §6.6 |
| 置信度/兜底 | §6.2、§13.5 |
| 查询打分/降级 | §13.2–§13.3 |
| Pack 卡片结构 | `query-response.schema.json` 的 card 子集 |
| 编译操作 | `ingest-ops.schema.json` |
| 冲突/Pin | `conflict.schema.json`、`pin.schema.json` |

**唯一新增**：`pack` 这一层物化快照，不改变页面契约。
