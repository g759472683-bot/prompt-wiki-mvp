# Prompt Wiki MVP — W1 交付物：LLM Wiki Schema 契约 v1.0

> 目标：让"被提问 → 1 秒内给出一张能开口、有依据的提词卡"变成一套**可编译、可审核、可追溯**的工程契约，而不是一堆 prompt。

这个目录是 W1 的开发输入，包含四样东西：

1. **契约主文档**：页面类型、字段、编译、Pin、冲突、Lint、查询的完整规范；
2. **机器可读 schema**：页面 / 编译操作 / Pin / 冲突 / 查询响应；
3. **8 个页面模板**：可直接复制给后端与算法同学；
4. **一个可校验的最小 Wiki**：从源文档、编译批次、人工审核、冲突、Pin 到最终提词卡，全链路示例。

---

## 当前状态（2026-10-26）

- **产品形态**：L3——Wiki 隐形，用户只看到"卡包 / 卡 / 依据 / 复盘"。
- **已完成**：Wiki Schema v1.0、L3 PRD v0.1、技术方案 + API v0.1、GitHub 竞品扫描。
- **D1–D5**：后端骨架 + DeepSeek 编译 + 异步 job + 审核/发布已**本地跑通**：33 个测试通过；5 份文档 → 每份 4–6 页 + **12–15 张卡**，42–93s/份；真实异步 E2E：入队 → worker → 5 页 + 12 卡 → 批准 17 页 + pack，0 collision。
- **Android**：v0.1 已在 Redmi K80 真机跑通；**v0.6.0 APK 已构建**（65MB，arm64），新增"L2 1–4 条可点开论证详情 + 追问预案 + 逐条置信度 + 论点 Pin + 无依据 LLM 开关 + 离线 Vosk 中文语音"；含批量导入、`/v1/ask` 混合召回兜底、Web 后台、APK 发布。
- **v0.4 新增**：跨文档一致性扫描（Web“一致性”/App 首页提示）、论点级人工修改/Pin、按 `green/yellow/red` 分档的反馈校准（每档 ≥5 条才生效）。`pack-20261025-06` 已重编译为展开版。
- **双端互通**：邀请码 = 工作区；手机和 Web 同一邀请码共享文档/任务/卡包；旧数据已迁移到 `W1-DEMO`。
- **Web 后台**：`http://192.168.137.1:8000/admin`（文档/任务/审核/卡包/一致性/校准/APK 发布）。
- **APK**：`http://192.168.137.1:8080/app-debug.apk`；发布接口 `GET /v1/app/latest`。
- **已按默认写死（W1 可推翻）**：L1 0.8s、Pin 只做 field、P0 手动触发、首发内测以路演/答辩为主、面试做 dogfood。
- **下一步**：v0.2 真机回归 → 云端 ASR（等 key）→ D6 场景 prep / 逐张审核 / story/entity / Pin/冲突/Lint。

## 1. 文件地图

| 路径 | 内容 | 谁看 |
|---|---|---|
| [`docs/wiki-schema-contract-v1.0.md`](docs/wiki-schema-contract-v1.0.md) | **主契约**（先读这个） | 全员 |
| [`docs/prd-v0.1-l3.md`](docs/prd-v0.1-l3.md) | **L3 产品需求**：四个界面、流程、P0、指标、8 周计划 | 全员 / 决策 |
| [`docs/architecture-api-v0.1.md`](docs/architecture-api-v0.1.md) | **技术方案 + API**：编译/出包/运行时、Pack 契约、Android 要点 | 后端 / Android |
| [`docs/baseline-d4.md`](docs/baseline-d4.md) | **五文档基线**：页面/卡片数量、token/耗时、已修问题与剩余风险 | 全员 |
| [`docs/android-mvp-plan.md`](docs/android-mvp-plan.md) | **Android MVP 计划**：交付时间、范围、10 天拆解、构建方式与风险 | 全员 / 决策 |
| [`docs/v0.2-feedback-plan.md`](docs/v0.2-feedback-plan.md) | **v0.2 反馈落地**：语音/RAG/批量/Web/APK 升级的方案与状态 | 全员 / 决策 |
| [`docs/v0.3-argument-cards.md`](docs/v0.3-argument-cards.md) | **v0.3 论证卡**：L2 可展开、论点详情、追问、置信度规则 | 产品 / 后端 / Android |
| [`docs/v0.4-consistency-pins-calibration.md`](docs/v0.4-consistency-pins-calibration.md) | **v0.4**：跨文档自洽、论点 Pin、置信度分档校准与边界 | 全员 |
| [`docs/offline-asr-options.md`](docs/offline-asr-options.md) | **离线 ASR 选型**：Vosk / sherpa-onnx / Whisper / FunASR / WeNet 对比与选择 | 产品 / Android |
| [`schema/page.frontmatter.schema.json`](schema/page.frontmatter.schema.json) | 页面 frontmatter 的 JSON Schema | 后端 / 算法 |
| [`schema/ingest-ops.schema.json`](schema/ingest-ops.schema.json) | Ingest 操作计划（CREATE/UPDATE/LINK/NOOP/CONFLICT/NEEDS_HUMAN） | 后端 / 算法 |
| [`schema/pin.schema.json`](schema/pin.schema.json) | 人工修正账本 | 后端 |
| [`schema/conflict.schema.json`](schema/conflict.schema.json) | 冲突记录 | 后端 |
| [`schema/query-response.schema.json`](schema/query-response.schema.json) | 提词查询 `done` 帧（Android 契约） | Android / 后端 |
| [`templates/`](templates/) | 8 类页面模板 | 全员 |
| [`examples/wiki/`](examples/wiki/) | 端到端示例 Wiki（15 页 + 2 冲突 + 3 Pin + 1 次完整 run） | 全员 |
| [`tools/validate_wiki.py`](tools/validate_wiki.py) | 参考校验器（stdlib + PyYAML） | 后端 / CI |
| [`backend/`](backend/README.md) | **后端**：认证/工作区、上传、解析、引用校验、DeepSeek 页面+卡片编译、异步 job、审核/发布、`/v1/ask` 混合召回、Web 后台、APK 发布 | 后端 |
| [`android/`](android/README.md) | **Android v0.6**：登录、批量上传、job、批准、现场提词、引用、论点展开/Pin、校准置信度、离线 Vosk 语音、更新检查；APK 在 `dist/` | Android / 测试 |
| [`docker-compose.yml`](docker-compose.yml) | 本地/内测一键起服务 | 后端 |
| [`research/github-landscape-2026-10.md`](research/github-landscape-2026-10.md) | GitHub 竞品扫描：LLM Wiki 集群、实时提词集群、差异点与 8 周计划调整建议 | 全员 / 决策 |

## 2. 30 分钟阅读顺序

1. 主文档 §0–§1：三条红线与七条原则（5 分钟）。
2. §5–§6：页面类型、frontmatter、置信度规则 `rule_v1`（10 分钟）。
3. §9–§12：Ingest / Pin / 冲突 / Lint 的**机器约束**（10 分钟）。
4. §13：查询契约与延迟预算（5 分钟）。
5. 打开 `examples/wiki/`，按 §16 的 9 步走查（10 分钟）。

## 3. 一句话说清数据形状

```text
source（原文 block，不可改）
  └─ evidence（source + block + 逐字 quote）
       ├─ claim（一条可断言结论）
       ├─ story（一个可讲案例）
       └─ metric（一个数字与口径）
            └─ qa.card（L1 关键词 / L2 骨架 / L3 正文 / 兜底）
                 └─ scenario.questions（会前 Top20，优先级 + 必答）
```

- ID 形如 `qa:biggest-failure`，**不可变**；路径只是投影。
- 页面只认 ID 链接，`[[claim:ledger-migration-led]]`。
- 查询热路径只读 `qa.card` 与本地缓存，**不调 LLM**。
- 冲突只记录不裁决；Pin 是人工权威，重编译时逐条对账。

## 4. 我在你原始清单上补的 8 个决策（请确认）

你的清单已经定了架构方向，但有些"一旦写进代码就难改"的细节，我先替你定了。不同意就直接推翻，改动成本在 W1 最低。

| # | 决策 | 理由 | 不同意会怎样 |
|---|---|---|---|
| 1 | 页面分 **8 类**：index / source / entity / claim / story / metric / qa / scenario | 每类都有独立的编译与查询职责，避免"万能页" | 类型更少 → 编译 prompt 更难约束；更多 → 索引与审核成本上升 |
| 2 | L1/L2 存在 **qa 的 frontmatter**，L3 是正文 | 查询零解析、卡片随页面一起审核 | 存独立卡片文件 → 双写不一致、审核要跑两处 |
| 3 | Pin 支持 **field / section** 两种锚点，`/body` 为保留路径 | 90% 修正是改某句话；整页 Pin 会冻结页面 | 只做整页 Pin → 页面很快不可维护 |
| 4 | **没有类型化关系边**；`LINK` 只做索引/场景挂载 | MVP 不需要图查询，专用字段已承载语义 | 引入 `supports/part_of` → 人工维护词表，收益低 |
| 5 | 绿色 = **2 个独立来源 + 人审 + 无冲突 + 未过期**，人审不能把黄变绿 | 可信度必须可解释，否则"绿"会通胀 | 放宽 → 用户第一次被戳穿就不再信红黄绿 |
| 6 | 冲突 **6 种 kind**（数值/口径/事实/时效/身份/重复），`resolution` 必须 `human:*` | 自动裁决是产品自杀；CI 断言自动覆盖率为 0 | 允许自动选择 → 现场说错数字 |
| 7 | 审核时"编辑后通过" **自动生成 Pin** | 人工修正的主要来源就是审核；否则改一次丢一次 | 手动建 Pin → 静默丢失率不可能为 0 |
| 8 | 索引页用 `AUTO` 区块，编译器只改区块内、只增不删 | 人工导语与自动目录共存，不需要 Pin | 整页生成 → 人工调整每次被冲掉 |

另外三个明确取舍：

- **不上向量库**：先用"场景索引 + 问题变体 + FTS5 BM25"，触发条件写在 §13.2。
- **查询不做自动问题检测**：P0 手动触发（点按/耳机键），自动检测留 P1。
- **单用户**：多人协作、权限模型留到 W8 后再谈。

## 5. 示例怎么读

`examples/wiki/` 是一个虚构但自洽的面试场景（林舟 → 云栖科技 后端负责人）：

- 3 份来源、2 个实体、2 条断言、1 个案例、1 个指标、3 张问答卡、1 个场景；
- 2 个未决冲突：可用性 99.99% vs 99.95%、"零故障" vs P1；
- 3 条 Pin：改措辞、改兜底、禁用语；
- 1 次完整 Ingest run：10 个操作，含 `NOOP` 与 `NEEDS_HUMAN`；
- 2 个查询快照：红色卡片（必须优先兜底）与 BM25 降级卡。

看这一页就能理解产品价值：**同一个"最大失败"问题，系统既不让用户说假话，又能在 1 秒内给出一句能开口的话。**

## 6. 本地校验

```bash
pip install pyyaml
python tools/validate_wiki.py examples/wiki
# 期望输出：OK：0 个错误，0 个警告
```

校验器覆盖：ID/断链、证据逐字命中、置信度红线（冲突未决必须红、绿色必须 2 来源+人审）、卡片条数与字数、卡片数字追溯、Pin 锚点是否生效、冲突主体状态、查询快照引用、Lint 门禁一致性。

> 说明：`examples/` 中的 `sha256` 是格式合法的**示例占位值**，不是真实文件哈希；真实导入时由解析器计算。校验器已在本机执行：`页面 15 · 冲突 2 · 0 错误 0 警告`。

## 7. 一个必须确认的口径冲突

你的一句话说"1 秒内给提词卡"，阶段目标写"L1 1.5 秒、完整卡 3 秒"，验收表写"L1 0.8s / L2 1.5s / L3 3s"。**本契约按最严的验收表写**（L1 0.8s）。如果真实目标是 1.5 秒，L1 预算可以放宽，但缓存与预取策略会相应简化——这个数直接决定 W6–W7 的性能工作量，建议 W1 就定死。

## 8. 下一步（按你定的顺序）

1. **PRD v0.1**：把 P0 功能、不做清单、三条红线写成可验收的页面流程。
2. **API 清单**：导入、编译、审核、查询、会话、反馈——请求/响应直接复用本目录的 schema。
3. **技术验证（3–5 天）**：拿 5–10 份真实文档跑 Ingest，人工逐页看 diff，记录：重复率、引用命中率、红黄绿分布、单文档成本、编译耗时。
4. **W2–W3**：Ingest 流水线落地；W2 先只做 `field` 锚点 Pin，`section` 放 P1。

**W1 冻结前必须拍板的 5 件事**（详见主文档 §17）：

- 8 类页面是否就定这些？
- 绿色门槛是否接受"2 独立来源 + 人审"？
- Pin 是否先只做 `field` 锚点？
- Top20 预测问题由编译期还是会前单独 run 生成？
- 是否允许用户手工创建 qa 页？

---

**版本**：v1.0（Freeze Candidate）· **契约变更**：破坏性变更必须升 `schema_version` 并提供迁移脚本。
