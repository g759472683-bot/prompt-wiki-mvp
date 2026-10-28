# LLM Wiki Schema 契约 v1.0

> **状态**：W1 冻结候选（Freeze Candidate）· **适用**：后端编译/查询服务、Android 提词卡渲染
> **唯一事实源**：Markdown + YAML frontmatter。SQLite / FTS5 只是可重建的派生索引。
> **变更规则**：破坏性变更必须升 `schema_version` 并附迁移脚本（见 §14）。

---

## 0. 这份文件要回答的五个问题

一个"被提问 → 1 秒内能开口"的提词系统，成败不在模型，而在**知识以什么形状被存下来**。本契约只回答五件事：

1. **什么算一页？** —— 页面类型与粒度（§5）
2. **机器读哪些字段、人读哪些字段？** —— frontmatter 规范（§6）
3. **LLM 能改什么、绝对不能改什么？** —— Ingest 操作契约（§9）
4. **人改过的东西，怎么在重编译中活下来？** —— Pin 契约（§10）
5. **查询在 0.8 秒内到底读什么？** —— Query 契约（§13）

**本文件不覆盖**：UI 视觉稿、ASR 接入、HTTP 路由与鉴权、提示词工程细节（附录 A/B 只给基线版本）。这些分别属于 PRD、API 清单与实现文档。

### 0.1 三条不可协商的红线

| # | 红线 | 违反后果 | 强制手段 |
|---|---|---|---|
| R1 | 没有 source block 引用的事实，不得进入证据区、不得进入卡片 | 幻觉率失控，产品信任一次性烧掉 | 校验门禁：`evidence` 为空 / 引用不可解析 → 拒绝提交 |
| R2 | 冲突不自动裁决；Pin 不静默丢失 | 用户不敢改，改了也白改 | 冲突 `resolution` 必须由 `human:*` 写入；Pin ledger 对账，孤儿 Pin 阻断该页提交 |
| R3 | 查询热路径不出网、不调 LLM | 1 秒承诺变成 3 秒，现场翻车 | 命中路径只读本地缓存；LLM 仅用于未命中兜底与措辞适配 |

---

## 1. 七条设计原则

| # | 原则 | 含义 | 直接约束 |
|---|---|---|---|
| P1 | Wiki 是编译产物，不是原文镜像 | 页面只服务"被问到时能否开口"，不追求知识完整 | 不建"文档摘要页"；摘要留在 source 页 |
| P2 | 一页一个可复用单元 | claim 一页一断言，story 一页一案例，qa 一页一问 | 一页出现两个独立断言 → 拆页 |
| P3 | 一切结论可落到 block | 每句证据都能定位到原文某一段 | 证据必须带 `source + block + quote` |
| P4 | 人是唯一裁决者 | 冲突、覆盖、删除都需人工动作 | LLM 无 `resolve`、无 `delete` 权限 |
| P5 | 重编译幂等 | 同输入、同版本、同 prompt → 同结果 | run_key 去重；人工修正外置为 Pin |
| P6 | 稳定 ID + 可变路径 | 链接认 ID，移动文件不破链 | `id` 不可变；路径只是投影 |
| P7 | 热路径零 LLM | 命中即读预编译卡片 | L1/L2 编译期生成，查询期只读取 |

**为什么不上向量库**：MVP 的知识规模是 100–500 页，问题域是"我自己的经历"，命中靠**问题变体 + 场景索引 + BM25**已经够用；引入向量库会增加 embedding 漂移、版本迁移和一次额外的网络/计算开销，与 0.8s 目标冲突。触发重新评估的条件写在 §13.2.4。

---

## 2. 术语

| 术语 | 定义 |
|---|---|
| **Page（页面）** | 一个带 frontmatter 的 Markdown 文件，是 Wiki 的最小知识单元 |
| **Block（块）** | source 页中被解析出的原文段落，ID 形如 `b-0007`，带页码/字符偏移 |
| **Evidence（证据）** | `{source, source_version, block, quote, verified}` 四元组，指向 block 内的一段逐字引用 |
| **Card（提词卡）** | qa 页上的三段式输出：L1 关键词、L2 骨架、L3 正文；L1/L2 编译期生成 |
| **L1 / L2 / L3** | L1 = 3–5 个可扫读关键词（≤0.8s）；L2 = 3–5 条可开口骨架（≤1.5s）；L3 = 证据与展开（≤3s） |
| **Pin（钉子）** | 人工对某字段/某句话的权威修正，重编译时必须保留 |
| **Conflict（冲突）** | 两条来源对同一事实给出不兼容说法，需人工裁决的记录 |
| **Lint** | 对断链、缺证据、过时、重复、冲突未决等问题的定期体检 |
| **Run（编译批次）** | 一次 Ingest 的完整执行记录，含 manifest / ops / review / diff / pin-ledger |
| **Staging** | 编译草稿区，未审核内容不得进入正式 Wiki |
| **Revision** | 页面内容版本号，整数递增；卡片用它判断是否过期 |

---

## 3. 存储布局

```text
wiki/
├── index.md                          # 根索引（index:root）
├── indexes/<domain>.md               # 领域索引（index:career 等）
├── pages/
│   ├── entity/<slug>.md
│   ├── claim/<slug>.md
│   ├── story/<slug>.md
│   ├── metric/<slug>.md
│   ├── qa/<slug>.md
│   └── scenario/<slug>.md
├── sources/
│   ├── <slug>.md                     # 当前版本
│   └── _archive/<slug>@v<n>.md       # 历史版本，只读，保证旧引用可解析
├── pins/<type>__<slug>.yaml          # 每页一个人工修正账本
├── conflicts/<conflict_id>.yaml
├── lint/<lint_run_id>.yaml
├── runs/<run_id>/
│   ├── manifest.yaml
│   ├── ops.json                      # LLM 产出的操作计划
│   ├── diff.md                       # 人审用的差异说明
│   ├── review.yaml                   # 人的裁决记录
│   └── pin-ledger.yaml               # Pin 对账结果
├── meta/schema_version.yaml
└── .staging/<run_id>/                # 草稿，审核通过后原子写入
```

### 3.1 命名规则

- **ID**：`<type>:<slug>`，如 `qa:why-this-role`。slug 为 `[a-z0-9]+(-[a-z0-9]+)*`，≤48 字符，**创建后不可变**。
- **文件路径**：由 ID 机械推导，`:` 换成目录层级。`qa:why-this-role` → `pages/qa/why-this-role.md`。
- **Windows 兼容**：文件名不得含 `: * ? " < > |`。Pin 文件名用 `__` 代替 `:`（`pins/qa__biggest-failure.yaml`），冲突/运行 ID 只用 `[a-z0-9-]`。
- **大小写**：slug 全小写；标题大小写不影响 ID。

### 3.2 谁可以写什么

| 文件 | 编译器 | 人（审核/编辑） | 备注 |
|---|---|---|---|
| `sources/**` | 创建新版本 | 只可改 `trust` 与 `notes` | 正文 block 不可改，改了引用就断了 |
| `pages/**` | 生成草稿，审核通过后写入 | 可直接编辑（自动生成 Pin） | 人工编辑必须走 UI，留下 review 记录 |
| `pins/**` | 只读、校验 | 创建/停用 | 卸载 Pin 必须留 `retired` 记录 |
| `conflicts/**` | 创建、追加审计 | 裁决、关闭 | 编译器不得写 `resolution` |
| `index.md` / `indexes/**` | 维护 `AUTO` 区块 | 可写区块外内容 | 见 §7.4 |
| `runs/**` | 写入 | 只读 | 审计留痕 |

---

## 4. ID、链接与图

### 4.1 八种页面类型

| 类型 | 回答的问题 | 粒度 | 典型数量（个人库 200 页） |
|---|---|---|---|
| `index` | 从哪开始找？ | 领域 / 全局 | 5–15 |
| `source` | 这句话从哪来？ | 一份原始文档 | 20–40 |
| `entity` | 这是谁/什么？ | 一个人/公司/项目/概念 | 30–60 |
| `claim` | 我能不能这么断言？ | 一条可验证断言 | 60–120 |
| `story` | 有什么案例可讲？ | 一个完整案例（STAR） | 10–20 |
| `metric` | 数字是多少、口径是什么？ | 一个指标 | 10–20 |
| `qa` | 被问到怎么答？ | 一个问句 | 40–80 |
| `scenario` | 这场会怎么准备？ | 一场面试/路演/会议 | 每场 1 页 |

### 4.2 链接语法

- 正文中使用 `[[<id>]]` 或 `[[<id>|显示文本]]`，如 `[[claim:ledger-migration-led|分库迁移]]`。
- 链接目标必须是已存在的页面（`draft/active/stale` 均可）；链到 `retired` 页面产生 Lint 警告。
- **只认 ID，不认路径**。重命名页面只改路径，不改 ID；禁止用相对路径当链接。
- 反向链接由编译器扫描生成到 SQLite，不在页面里手写。
- 外链用普通 Markdown 链接；**不得**把外部 URL 当作证据来源，必须先把内容导入为 source 页。

### 4.3 为什么没有"关系类型"

MVP 不引入 `supports / part_of / contradicts` 这类类型化边。理由：类型化边需要人工维护词表，而 MVP 真正需要的语义已经由专用字段承载——证据在 `evidence`，场景归属在 `scenario.questions`，冲突在 `conflicts`，其余只是导航。等出现"必须按关系类型查询"的真实需求再升级。

> `LINK` 操作因此只做**导航挂载**（把已有页面挂到索引或场景），不做知识合并，见 §9.4。

### 4.4 页面生命周期

```text
        ┌─────────┐ 人工审核通过   ┌────────┐  证据过期/来源更新   ┌───────┐
        │  draft  │ ───────────▶ │ active │ ──────────────────▶ │ stale │
        └─────────┘               └────────┘                     └───────┘
             │                        │                              │
             │ 驳回                   │ 被新页取代                    │ 人工复核
             ▼                        ▼                              ▼
          （丢弃）                 retired ◀──────────────────── active
```

| 状态 | 含义 | 查询行为 |
|---|---|---|
| `draft` | 编译器生成、未经人审 | 不进入正式查询；仅审核预览 |
| `active` | 人工确认，可对外使用 | 正常命中 |
| `stale` | 证据过时或来源更新，尚未复核 | 可命中但强制黄色/红色 + 兜底提示 |
| `retired` | 被取代或主动废弃 | 不命中；历史引用保留可解析 |

---

## 5. 页面类型细则

### 5.1 `index` — 导航索引

- **用途**：让"读索引"这一动作有明确入口，而不是让 LLM 自由扫全库。
- **结构**：根索引列领域与场景；领域索引列该领域的 claim / story / metric / qa，按主题分组。
- **何时创建**：新领域（职业、项目、行业认知）出现且页面 ≥5 时；场景索引不单独建页，直接挂在根索引。
- **禁止**：把索引页写成知识页；索引只放链接与一行摘要。

### 5.2 `source` — 来源页

- **用途**：保存可追溯的原文块，是全部证据的锚点。
- **何时创建**：每次导入文档创建一个版本页；重新导入生成 `v+1`。
- **关键约束**：正文 block 不可编辑；旧版本进 `_archive/`，保证历史引用永远可解析。
- **证据质量**：`trust` 由人设定（`high` 官方/自撰且可核对；`medium` 第三方转述；`low` 营销稿/未核实）。`low` 来源不得单独支撑绿色置信度。

### 5.3 `entity` — 实体页

- **用途**：人物、公司、项目、产品、概念的一句话定义与关键事实。
- **何时创建**：某实体在 ≥2 个页面被提及，或面试/路演对手方需要背景。
- **禁止**：把 entity 页写成百科；只写"与我的叙事相关"的事实。

### 5.4 `claim` — 断言页

- **用途**：把"我能不能这么说"变成可审计对象。一条断言一页。
- **何时创建**：某个说法会出现在卡片或回答里，且需要证据支撑。
- **关键约束**：`statement` 必须是一句可判真假的陈述；`scope` 必须写清适用边界；`evidence` ≥1。
- **反例**："我技术很强" —— 不可判定，拆成"主导过日均 2.3 亿笔的账务迁移"。

### 5.5 `story` — 案例页

- **用途**：面试/路演中最值钱的可讲述单元，固定 STAR 结构，便于现场按骨架展开。
- **何时创建**：一个能讲 60–120 秒、含冲突与结果的完整案例。
- **关键约束**：必须有"我的动作"与"可验证结果"；结果中的数字必须来自 metric 或有 evidence。

### 5.6 `metric` — 指标页

- **用途**：所有数字的唯一出口，避免同一指标在不同页面出现不同口径。
- **何时创建**：任何会被说出口的数字（可用性、QPS、成本、增长、团队规模）。
- **关键约束**：`metric.key` 全局唯一（用于跨页冲突检测）；必须写口径与算法；`value_num` 与 `value` 必须一致。

### 5.7 `qa` — 问答页（提词卡载体）

- **用途**：查询热路径唯一直接读取的知识类型。
- **何时创建**：会前预测问题、复盘发现的高频问题、用户手动新增问题。
- **关键约束**：`card.l1/l2` 编译期写死；`evidence_refs` 指向 claim/story/metric/entity；卡片中每个数字必须能在引用页的证据里找到。
- **禁止**：qa 页里写"通用鸡汤"；L2 超过 5 条（现场读不完）。

### 5.8 `scenario` — 场景页

- **用途**：一场会前的作战地图：对方是谁、我要什么、哪些问题必须答、哪些话不能说。
- **何时创建**：每次面试/路演/重要会议一页。
- **关键约束**：`questions` 最多 20 条并按优先级排序；`must_hit` 的问题必须有 active 的 qa 页且卡片未过期，否则 Lint 阻断"会前准备完成"。

---

## 6. Frontmatter 规范

### 6.1 通用字段（所有类型）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `schema_version` | string | ✅ | 固定 `"1.0"`；不匹配的页面拒绝加载 |
| `id` | string | ✅ | `<type>:<slug>`，不可变 |
| `type` | enum | ✅ | 8 类之一，必与目录一致 |
| `title` | string | ✅ | ≤40 字，人读标题，不用于匹配 |
| `summary` | string | ✅ | ≤80 字，一句话；索引领与 BM25 的主要语料 |
| `status` | enum | ✅ | `draft / active / stale / retired` |
| `language` | string | ✅ | 默认 `zh-CN`，为多语言预留 |
| `revision` | int | ✅ | ≥1，内容变更时 +1；卡片用它判断是否过期 |
| `created_at` | datetime | ✅ | ISO 8601 带时区 |
| `updated_at` | datetime | ✅ | 同上 |
| `created_by` | string | ✅ | `compiler` 或 `human:<name>` |
| `run_id` | string \| null | ✅ | 最近一次写入的编译批次；纯人工创建且未编译为 `null` |
| `tags` | string[] | ⬜ | 主题标签，≤8 个，用于索引分组与检索 |
| `review` | object | ⬜ | `{reviewed_by, reviewed_at, review_run}`；绿色置信度必需 |
| `freshness` | object | ⬜ | `{valid_from, valid_until, review_after}`，日期或 null |
| `confidence` | object | 知识页 ✅ | `{level, reasons[], rule, computed_at}` |
| `evidence` | array | claim/story/metric/entity ✅ | 见 §6.7 |
| `conflicts` | string[] | ⬜ | 影响本页的冲突 ID（编译器维护） |
| `conflict_state` | enum | ⬜ | `none / open / resolved`；本页是冲突主体时置 `open` |
| `aliases` | string[] | entity ⬜ | 别名，用于检索；不用于 ID |
| `notes` | string \| null | source ⬜ | 人工备注（唯一允许人改的 source 字段之一） |

> **不要**在页面里手写 `links`、`backlinks`、`pins`、`card.built_from` 之外的派生缓存。派生数据一律进 SQLite。

### 6.2 置信度 `rule_v1`

置信度不是模型自评，是**确定性规则算出来的**。`confidence.level` 只允许 `green / yellow / red`，`reasons` 只能取下列理由码。

#### 6.2.1 判定顺序

先判红，再判绿，其余为黄。

**RED（任一成立）**

| 条件 | 理由码 |
|---|---|
| 本页 `conflict_state: open` | `open_conflict` |
| qa 页的 `conflicts` 中含任一 open 冲突（卡片涉及未决事实） | `open_conflict` |
| `evidence` 为空（知识页） | `no_evidence` |
| 全部证据 `verified: false` | `unverified_quote` |
| 全部来源 `trust: low` | `low_trust_source` |
| `freshness.valid_until` 已过 | `expired` |

**GREEN（全部成立）**

| 条件 | 理由码 |
|---|---|
| 去重后独立来源 ≥2，且全部 `verified: true` | `two_sources` |
| 无 open 冲突，且无证据 quote 与冲突变体重叠 | `no_conflict` |
| `review.reviewed_by` 以 `human:` 开头 | `human_reviewed` |
| 未过 `valid_until` / `review_after` | `fresh` |
| （仅 qa）所有 `evidence_refs` 指向的页面均为 green | `refs_green` |

**YELLOW（其余情况）**

| 条件 | 理由码 |
|---|---|
| 独立来源只有 1 个 | `single_source` |
| 部分证据 `verified: false`（但非全部） | `partial_unverified` |
| 证据 quote 与某个 open 冲突变体的 quote 重叠 | `disputed_evidence` |
| 查询期兜底组装（仅卡片，不写回 Wiki） | `degraded` |
| 已过 `review_after` 但未过 `valid_until` | `review_due` |
| 未经人工审核 | `unreviewed` |
| （仅 qa）任一 `evidence_refs` 为 yellow | `ref_yellow` |

#### 6.2.2 四个容易吵的点，先定死

1. **同一份文档的多个 block 只算一个来源。** 独立来源按 `source.id` 去重。
2. **人工审核不能把黄变绿。** 审核是绿色的必要条件，不是充分条件；否则"我审过了"会变成万能通行证。
3. **卡片置信度 = min(引用页置信度)，且 qa 自身冲突可再降级。** 不存在"卡片比证据更可信"。
4. **冲突污染按 quote 算，不按 block 算。** 同一 block 里只有"迁移方式"和"零故障"两句时，引用前一句的 claim 不因后一句的冲突降级；否则一个 block 出事会拖垮全库。

#### 6.2.3 示例

```yaml
confidence:
  level: yellow
  reasons: [single_source, review_due]
  rule: rule_v1
  computed_at: 2026-10-25T10:20:00+08:00
```

### 6.3 状态机与新鲜度

| 当前 | 事件 | 新状态 | 执行者 |
|---|---|---|---|
| `draft` | 审核通过 | `active` | 人 |
| `draft` | 驳回 | 丢弃（不落库） | 人 |
| `active` | 证据来源发布新版本 / 冲突未决 / 人工标记 | `stale` | 编译器或人 |
| `stale` | 复核通过 | `active` | 人 |
| `active` / `stale` | 被新页 `supersedes` | `retired` | 人 |
| `retired` | — | 不可逆（可新建页） | — |

**新鲜度字段**

```yaml
freshness:
  valid_from: 2026-01-01
  valid_until: 2026-12-31   # 过期即 red，查询仍可用但必须提示
  review_after: 2026-11-30  # 到期转 yellow，不阻断
```

- `valid_until` 用于"会变的事实"（可用性、团队规模、融资额）；到期必须重编译而不是猜。
- `review_after` 用于"大概不会变但需复查"的页面（故事、项目背景）。
- 查询时若页面在库中仍为 `active` 但已过 `valid_until`，按 `stale` 处理并强制红色兜底（不依赖 Lint 是否跑过）。

### 6.4 证据结构

```yaml
evidence:
  - source: source:resume-2026
    source_version: 1
    block: b-0004
    quote: "主导账务平台分库分表迁移：按商户 ID 分片、双写 6 周、灰度放量，覆盖 12 个服务、日均 2.3 亿笔"
    role: primary        # primary | supporting | counter
    verified: true       # quote 是否逐字命中 block
```

| 规则 | 说明 |
|---|---|
| 逐字 | `quote` 必须是 block 文本的连续子串；允许省略号？**不允许**。要省略就截短，不能拼接两段 |
| 长度 | 20–120 字；超过 120 字说明这一段不该整段当证据 |
| 不翻译 | 原文是英文就保留英文；中文解释放正文，不得替换 quote |
| 数字原样 | 数字、单位、百分号必须与原文一致（`99.95%` 不能写成 `99.9%`） |
| `role` | `primary` 直接支撑；`supporting` 补强；`counter` 反证（用于冲突页） |
| `verified` | 编译器机械比对后写入；人工抽查可改 false，触发黄色 |

### 6.5 各类型专有字段

#### `index`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `index_scope` | enum | ✅ | `root / domain` |
| `domain` | string | domain 时 ✅ | 如 `career`，与文件名一致 |

#### `source`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `source.doc_id` | string | ✅ | 稳定文档 ID；重新导入沿用 |
| `source.filename` | string | ✅ | 原文件名 |
| `source.mime` | string | ✅ | `application/pdf` 等 |
| `source.sha256` | string | ✅ | 64 位十六进制，用于去重与版本判定 |
| `source.bytes` | int | ⬜ | 文件大小 |
| `source.pages` | int | ⬜ | 页数 |
| `source.imported_at` | datetime | ✅ | |
| `source.parser` | string | ✅ | `pdfplumber / docx2txt / markdown` |
| `source.parser_version` | string | ✅ | |
| `source.language` | string | ✅ | |
| `trust` | enum | ✅ | `high / medium / low` |
| `version` | int | ✅ | ≥1 |
| `supersedes` | string \| null | ✅ | 上一版本来源 ID（同 ID 不同 version 时为 null） |
| `archived_at` | datetime \| null | ✅ | 被新版本替换的时间 |
| `extraction` | object | ✅ | `{blocks, warnings[], coverage, ocr}` |

#### `entity`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `entity_kind` | enum | ✅ | `person / org / product / project / concept` |
| `aliases` | string[] | ⬜ | 别名、英文名、简称 |

#### `claim`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `statement` | string | ✅ | 一句可判真假的陈述，≤60 字 |
| `claim_kind` | enum | ✅ | `experience / capability / technical / commercial / customer / market` |
| `scope` | string | ✅ | 适用边界；必须写"不适用于什么" |
| `verification` | enum | ✅ | `verified / unverified`（是否有逐字证据） |

#### `story`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `story_kind` | enum | ✅ | `project / incident / conflict / achievement` |
| `role` | string | ✅ | 我的角色，如"技术负责人" |
| `period` | string | ✅ | `2025-03 ~ 2025-09` |
| `team_size` | int \| null | ⬜ | |
| `stack` | string[] | ⬜ | 技术栈 |
| `metrics` | string[] | ⬜ | 相关 metric 页 ID |

#### `metric`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `metric.name` | string | ✅ | 人读名称 |
| `metric.key` | string | ✅ | 全局唯一键，如 `availability`；冲突检测按它聚合 |
| `metric.value` | string | ✅ | 展示值，如 `99.95%` |
| `metric.value_num` | number | ✅ | 数值，用于比较 |
| `metric.unit` | string | ✅ | `% / ms / 笔/日 / 人` |
| `metric.direction` | enum | ✅ | `higher / lower`（越大越好/越小越好） |
| `metric.period` | string | ✅ | `2025`、`2025-09`、`近 12 个月` |
| `metric.method` | string | ✅ | 口径与算法 |
| `metric.scope` | string | ✅ | 统计范围 |

#### `qa`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `question` | string | ✅ | 规范问句，≤40 字 |
| `question_variants` | string[] | ✅ | 2–6 条口语/ASR 变体，覆盖不同问法 |
| `intent` | enum | ✅ | `factual / behavioral / technical / motivation / risk / commercial / hr / other` |
| `scenario_kinds` | enum[] | ✅ | `interview / pitch / meeting` |
| `answer.target_sec` | int | ✅ | 30 / 60 / 90 |
| `answer.tone` | enum | ✅ | `confident / honest / concise` |
| `card` | object | ✅ | 见 §6.6 |
| `evidence_refs` | string[] | ✅ | 1–4 个 claim/story/metric/entity ID |

#### `scenario`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `scenario_kind` | enum | ✅ | `interview / pitch / meeting` |
| `counterparty` | string | ✅ | entity ID |
| `scheduled_at` | datetime | ✅ | |
| `duration_min` | int | ✅ | |
| `goal` | string | ✅ | 一句话目标 |
| `audience` | string[] | ⬜ | 在场人 |
| `questions` | array | ✅ | `{qa, priority 1-3, must_hit, note}`，≤20 |
| `constraints` | object | ⬜ | `{do_not_claim[], must_mention[]}` |
| `prepared_at` | datetime \| null | ✅ | 最近一次会前准备完成时间 |
| `prep_run` | string \| null | ✅ | 对应 run_id |

### 6.6 卡片结构 `card`

```yaml
card:
  l1: ["商户 ID 分片", "双写 6 周", "灰度放量", "2.3 亿笔/日"]
  l2:
    - "账务 12 个服务，按商户 ID 分片"
    - "双写 6 周，灰度放量切换"
    - "日均 2.3 亿笔，迁移由我牵头"
  fallback: "细节我需要翻迁移方案再确认，先说我确定的：分片键是商户 ID，双写 6 周。"
  evidence_refs: [claim:ledger-migration-led, entity:ledger-platform]
  confidence:
    level: green
    reasons: [two_sources, no_conflict, human_reviewed, fresh, refs_green]
    rule: rule_v1
    computed_at: 2026-10-25T10:20:00+08:00
  built_from:
    - {id: claim:ledger-migration-led, revision: 3}
    - {id: entity:ledger-platform, revision: 2}
  do_not_say: ["零故障", "从没出过问题"]
```

| 约束 | 值 | 理由 |
|---|---|---|
| L1 条数 | 3–5 | 少于 3 不够提示，多于 5 扫不完 |
| L1 单条长度 | ≤12 字 | 一眼一个词 |
| L2 条数 | 3–5 | 现场只读骨架 |
| L2 单条长度 | ≤28 字 | 一口气能说完 |
| `fallback` | ≤100 字 | 兜底要能立刻开口，且必须诚实 |
| `evidence_refs` | 1–4 个 | 少了不可信，多了拖慢引用解析 |
| `do_not_say` | 0–5 条 | 明确禁止出现的表述（如绝对化承诺） |

**L2 的第一条必须是"开口句"**，不是背景。被问到时人最怕的是第一秒的空白。

### 6.7 什么字段是"计算出来的"

`confidence`、`conflicts`、`conflict_state`、`card.confidence`、`card.built_from`、`revision` 由编译器计算/维护。人工不得直接改；要改就改证据、改来源 `trust`、或走冲突裁决。

---

## 7. 正文写作规范

### 7.1 固定标题（Pin 锚点与查询定位都依赖它）

| 类型 | 必选标题（顺序固定） |
|---|---|
| claim | `## 一句话说法` `## 成立条件` `## 证据` `## 可能的反驳` |
| story | `## 情境 S` `## 任务 T` `## 行动 A` `## 结果 R` `## 复盘与边界` `## 追问预案` |
| metric | `## 口径` `## 计算方式` `## 为什么可信` `## 常见追问` |
| qa | `## 一句话回答` `## 展开` `## 证据` `## 边界与不知道` `## 追问预案` |
| entity | `## 一句话定义` `## 关键事实` `## 与我的关系` `## 关联页面` |
| scenario | `## 会前简报` `## 对方关注点` `## 我的三个目标` `## 风险与禁区` `## 问题清单` |
| source | 无固定标题；按导入顺序排列 block |
| index | 无固定标题；`AUTO` 区块由编译器维护 |

- 标题文字不可改（改标题会让 Pin 的 quote 锚点失效）；要调整结构就升 schema 版本。
- `## 证据` 区块**由编译器从 frontmatter 生成**，人工不得编辑。要改证据，改来源或新增 `counter` 证据。

### 7.2 引用标记

正文提到证据时用 `E1`、`E2` 对应 `## 证据` 中的编号，例如：

> 迁移覆盖 12 个服务，日均 2.3 亿笔（E1）。

校验规则：正文出现 `E<n>` 时，`n` 必须存在于证据列表；不允许悬空编号。

### 7.3 数字与措辞

| 规则 | 说明 |
|---|---|
| 数字必须有出处 | 卡片 L1/L2/兜底中的数字由 `L004` 自动校验；正文数字在审核时人工核对，同样必须有出处 |
| 不四舍五入 | 原文 `99.95%` 不能写成 `99.9%` 或"接近 100%" |
| 不绝对化 | 禁用"零故障""从未""行业第一""保证"，除非 quote 原文如此且已标为争议 |
| 区分事实与判断 | 判断句用"我认为/我的判断是"，不得伪装成事实 |
| 第一人称 | 用"我"，不用"我们"（个人 Wiki，避免夸大团队归因） |
| 中文为主 | 专有名词保留英文；不中英混排整句 |

### 7.4 索引的 AUTO 区块

```markdown
# 职业与项目

（人工写的导语可以放这里）

<!-- AUTO:BEGIN -->
## 项目案例
- [[story:ledger-migration-2025|账务平台分库迁移]] — 2025 · P1 复盘 · 30 秒可讲
<!-- AUTO:END -->
```

- 编译器只重写 `AUTO` 区块，区块外的人工内容永不覆盖。
- 编译器只增不删：页面 `retired` 后从区块移除，但保留在 `## 已归档` 列表。
- 因此索引页**不需要 Pin**；人工调整顺序请写在区块外。

### 7.5 长度上限

| 类型 | 正文字数 | 说明 |
|---|---|---|
| claim | 200–600 | 断言页不是论文 |
| story | 600–1800 | 能讲 60–120 秒 |
| metric | 200–500 | 口径写清即可 |
| qa | 400–1200 | L3 是展开，不是全文 |
| entity | 150–500 | |
| scenario | 300–1000 | |

---

## 8. 页面模板

`templates/` 下有 8 个可直接复制的模板。**模板是副本，规范以 §6/§7 为准**；模板中的 `{{...}}` 是占位符，不参与校验。

| 模板 | 对应类型 | 使用场景 |
|---|---|---|
| [`templates/index.md`](../templates/index.md) | index | 新建领域索引 |
| [`templates/source.md`](../templates/source.md) | source | 导入新文档 |
| [`templates/entity.md`](../templates/entity.md) | entity | 新建公司/项目/人物 |
| [`templates/claim.md`](../templates/claim.md) | claim | 新增一条可断言结论 |
| [`templates/story.md`](../templates/story.md) | story | 整理一个案例 |
| [`templates/metric.md`](../templates/metric.md) | metric | 新增一个数字 |
| [`templates/qa.md`](../templates/qa.md) | qa | 新增预测问题与卡片 |
| [`templates/scenario.md`](../templates/scenario.md) | scenario | 新建一场面试/路演 |

---

## 9. Ingest 契约（编译流水线）

### 9.1 八个阶段

| 阶段 | 输入 | 输出 | 用 LLM | 预算（初始值） | 失败处理 |
|---|---|---|---|---|---|
| S0 `PARSE` | 上传文件 | source 页 + block + sha256 + 警告 | 否 | ≤3s/10 页 | 解析失败 → 任务失败并提示换格式 |
| S1 `INDEX_READ` | 根索引 + ≤3 个领域索引 | 已存在的页面清单（id/title/summary） | 否 | ≤3k tokens | 索引缺失 → 从 SQLite 重建 |
| S2 `PLAN` | 文档摘要 + 索引清单 + 目标场景 | 操作骨架（不含正文） | 是 | ≤20 ops，≤8k tokens | 输出非法 → 重试 1 次 → 转人工 |
| S3 `WRITE` | 单个 op + 相关 block + 模板 | 完整页面草稿（staging） | 是 | ≤4k tokens/页 | 重试 2 次，仍失败 → `NEEDS_HUMAN` |
| S4 `VALIDATE` | staging + head | 校验报告 | 否 | ≤1s | 有 blocker → 不进入审核 |
| S5 `DIFF` | staging vs head | `diff.md` + 审核清单 | 否 | ≤500ms | — |
| S6 `REVIEW` | diff | `review.yaml`（批准/驳回/编辑） | 人 | — | 超时 48h → 运行标记 `expired` |
| S7 `COMMIT` | 批准的 op | 页面 / 冲突 / Pin / 索引更新 | 否 | ≤2s | 单页原子提交，失败回滚该页 |

### 9.2 Run 目录与 manifest

```yaml
# runs/run-20261025-02/manifest.yaml
schema_version: "1.0"
run_id: run-20261025-02
kind: ingest
status: completed_with_blockers   # running|completed|completed_with_blockers|failed|expired
started_at: 2026-10-25T10:02:11+08:00
finished_at: 2026-10-25T10:03:02+08:00
wiki_snapshot_at: 2026-10-25T10:00:00+08:00
inputs:
  - {source: source:postmortem-2025, version: 1, sha256: "..."}
index_read: [index:root, index:career]
model:
  name: deepseek-v3.1
  prompt_version: ingest-1.0.0
  temperature: 0
budget:
  ops_max: 20
  tokens_in: 48210
  tokens_out: 6210
  cost_usd: 0.038
stats:
  ops: 8
  created: 2
  updated: 1
  linked: 1
  noop: 1
  conflicts: 2
  needs_human: 1
  rejected: 0
timings_ms: {parse: 2100, plan: 15200, write: 28400, validate: 900, total: 51200}
```

### 9.3 上下文纪律

LLM **不能**自由浏览整个 Wiki。S1 只允许读：

1. `index:root` 全文；
2. 最多 3 个领域索引的 `AUTO` 区块；
3. 候选页面的 `title + summary + confidence.level`（不读正文）。

S3 生成单页时最多附带 40 个相关 block（按查询相似度挑选），且必须包含该 op 声明的全部证据 block。超出预算时先丢弃低相似度 block，**不得**丢弃证据。

### 9.4 决策矩阵

| 输入情况 | 操作 | 关键要求 |
|---|---|---|
| 内容已被现有页面完整覆盖 | `NOOP` | 必须写明覆盖页 ID；不得为了"有产出"硬造页面 |
| 新实体首次出现且与场景相关 | `CREATE entity` | 至少 1 条证据；单来源只能黄色 |
| 已有实体出现新事实 | `UPDATE entity` | 追加到"关键事实"，保留旧事实 |
| 同一断言出现新证据 | `UPDATE claim` | `evidence` 追加；重算置信度；不得改写 `statement` 除非证据要求 |
| 同一 `metric.key` 数值不同 | `CONFLICT` | 两个变体都保留；**禁止**覆盖 `value_num` |
| 数值相同但口径/范围不同 | `CONFLICT`（`scope_mismatch`） | 分别写清 scope，由人决定是否拆成两个 metric |
| 新问句，且现有页面能支撑 | `CREATE qa` + `LINK` 到场景 | 卡片数字必须可追溯 |
| 新案例，能讲 60 秒以上 | `CREATE story` | STAR 完整，结果有数字或可验证事实 |
| 新页面与旧页面语义重复（相似度 ≥0.6） | `NEEDS_HUMAN` | 建议合并方案，由人决定，不自动合并 |
| 证据不足、需要业务判断、涉及敏感表述 | `NEEDS_HUMAN` | 必须 `blocking: true`，不得静默跳过 |
| 新内容会覆盖已 Pin 的字段 | 允许生成 | 必须展示"将覆盖 Pin"；若语义冲突 → `CONFLICT` |

**明确禁止**：删除页面、修改 ID、修改 source 正文、自行裁决冲突、把低信任来源提升为绿色、生成没有 block 出处的数字。

### 9.5 操作 JSON

```json
{
  "schema_version": "1.0",
  "run_id": "run-20261025-02",
  "index_read": ["index:root", "index:career"],
  "ops": [
    {
      "op_id": "op-01",
      "op": "UPDATE",
      "target": "claim:ledger-migration-led",
      "base_revision": 3,
      "patch": [
        {"path": "/evidence/-", "value": {
          "source": "source:postmortem-2025",
          "source_version": 1,
          "block": "b-0005",
          "quote": "迁移由林舟牵头，架构方案无问题",
          "role": "supporting",
          "verified": true
        }}
      ],
      "reason": "复盘佐证迁移牵头人，补强原简历证据",
      "evidence": ["source:postmortem-2025#b-0005"]
    },
    {
      "op_id": "op-04",
      "op": "LINK",
      "from": "qa:biggest-failure",
      "to": "scenario:yunqi-backend-lead",
      "mount": "scenario",
      "position": {"priority": 1, "must_hit": true},
      "reason": "该问题是本场面试必问题"
    }
  ]
}
```

| 约束 | 说明 |
|---|---|
| `op_id` | 批次内唯一，按序执行 |
| `UPDATE` | 必须带 `base_revision`；不匹配则本 op 失败并重读页面，重试 1 次后转 `NEEDS_HUMAN` |
| `patch` | JSON Pointer；禁止 `remove`（不能删证据/段落），只能 `add/replace` |
| `CREATE` | 必须给 `type`、`id`、`staging_path`；内容不在 ops 里重复 |
| `LINK.mount` | 只允许 `index` / `scenario`；`scenario` 必须给 `priority` 与 `must_hit` |
| `CONFLICT` | 内嵌完整冲突记录（§11.3），`status` 只能为 `open` |
| `NEEDS_HUMAN` | 必须给 `question`、`options[]`、`blocking`；blocking 会阻止该批次"完成" |

### 9.6 生成约束（写进 prompt 的硬规则）

1. 只能引用给定 block；引用必须逐字，不得改写、拼接、翻译。
2. 每个数字必须来自 quote 或给定 metric；不确定就不写。
3. 不得创建新 ID 之外的结构；不得改名已有页面。
4. 不得写"行业领先""颠覆""保证"等无证据评价。
5. 页面长度服从 §7.5；L1/L2 服从 §6.6。
6. 冲突只记录，不选择；`resolution` 一律留空。
7. 低信任来源（`trust: low`）只能作为 `supporting` 或 `counter`，不得单独支撑页面。
8. 输出必须是合法 JSON，遵循 `schema/ingest-ops.schema.json`；不许多余字段。

### 9.7 校验顺序与重试

```text
schema → 链接存在性 → 证据可解析（source/version/block/quote 子串）
      → Pin 校验（§10.4） → 数字可追溯 → 冲突/策略（§9.4 禁止项）
```

任一步 blocker → 该 op 失败。生成类失败重试 1 次（把失败原因回灌 prompt）；结构性失败（证据不存在、ID 非法）不重试，直接 `NEEDS_HUMAN`。

### 9.8 人审界面必须呈现的 12 项

| # | 内容 | 为什么必须 |
|---|---|---|
| 1 | 操作类型与目标页 | 人要知道自己在改什么 |
| 2 | 触发原因（`reason`） | 防止"看起来像废话"的批量生成 |
| 3 | 逐字段 diff | 不看 diff 的审核等于没审 |
| 4 | 证据原文（可跳转到 source block） | 判断是否断章取义 |
| 5 | 置信度变化与理由码 | 黄色/红色要能解释 |
| 6 | 冲突提示（新增/仍 open） | 不能让人"顺手批准"一个矛盾 |
| 7 | Pin 影响（将覆盖哪几条、哪条会成孤儿） | 静默丢失就发生在这里 |
| 8 | 数字追溯结果（每个数字对应哪条证据） | 幻觉高发区 |
| 9 | 受影响的场景与卡片（哪些会过期） | 让代价可见 |
| 10 | token / 成本 / 耗时 | 控制编译预算 |
| 11 | 拒绝理由输入框 | 形成可复盘的负样本 |
| 12 | 批量操作范围（本页/本批） | 防止误点"全部通过" |

**审核动作语义**

| 动作 | 效果 |
|---|---|
| `approve` | 原样提交 |
| `edit_then_approve` | 提交人工版本，并**自动创建 Pin**（这是 Pin 最主要的来源） |
| `reject` | 丢弃该 op，记录拒绝理由；不影响其他 op |
| `acknowledge` | 仅对冲突/提示确认，不改变内容 |
| `defer` | 挂起，批次不能标记完成；到期提醒 |

### 9.9 提交原子性与回滚

- **单页原子**：一页的 frontmatter、正文、索引条目、Pin ledger 在同一事务内写入；失败则该页保持旧版本。
- **批次非原子**：被 Pin/冲突阻断的页面不阻止其他页面提交，但批次状态标 `completed_with_blockers`，且不得进入 `publish_allowed`。
- **journal**：`runs/<run_id>/journal.yaml` 记录每个页面的 old_revision → new_revision；回滚按 journal 逆序恢复。
- **卡片失效**：证据页 `revision` 变化 → 相关 qa 的 `card.built_from` 不匹配 → Lint `L013`，会前准备被阻断，直到重新生成卡片。

### 9.10 幂等与重放

```text
run_key = sha256(
  sorted(source_id@version) + prompt_version + model_name + schema_version
)
```

- 相同 `run_key` 直接返回已有 run，不重复计费。
- 重放（replay）必须显式指定 `run_id` + `force`，且生成新的 run 目录，不覆盖历史。
- 页面内容是否变化用 `revision` 判断，不用时间戳。

### 9.11 成本预算（初始值，W2–W3 校准）

| 指标 | 目标 |
|---|---|
| 单文档 ops | ≤20 |
| 单文档生成页面 | ≤8 |
| 单文档 tokens | ≤60k |
| 单文档成本 | ≤$0.15 |
| 单文档 P50 耗时 | ≤90s |

---

## 10. Pin 契约（人工修正的存活机制）

### 10.1 Pin 是什么、不是什么

- **是**：人对某个字段/某句话的权威修正，重编译时必须保留；是"人工修正静默丢失率 = 0"的实现手段。
- **不是**：版本控制、整页锁定、绕过审核的后门、解决冲突的工具。
- Pin 只作用于**本页**；跨页一致性靠 claim/metric 的单一出口，不靠 Pin 复制。

### 10.2 文件格式

```yaml
# pins/qa__biggest-failure.yaml
schema_version: "1.0"
page: qa:biggest-failure
updated_at: 2026-10-25T10:20:00+08:00
pins:
  - pin_id: pin-01JCF7R2K8N4Q6S9V1X3Z5B7D9
    anchor:
      kind: field                 # field | section
      path: /card/l2/0            # JSON Pointer，指向 frontmatter
    mode: replace                 # replace | must_include | must_exclude
    original: "2025 年迁移时出过一次 P1，很快就恢复了"
    value: "2025-09 账务迁移当晚出 P1，延迟 4 小时 12 分"
    reason: "不要淡化成'很快恢复'，时长要如实说"
    origin: review_edit           # review_edit | manual | migrated
    created_by: human:lin
    created_at: 2026-10-25T10:12:00+08:00
    source_run: run-20261025-02
    status: active                # active | pending_confirmation | orphaned | retired
```

### 10.3 锚点与模式

| 锚点 | 定位方式 | 适用 |
|---|---|---|
| `field` | JSON Pointer 指向 frontmatter 字段（含数组下标） | 卡片 L1/L2、statement、metric 值 |
| `field` + `/body` | 保留路径，表示正文整体 | 仅用于 `must_exclude` 全局禁用 |
| `section` | `heading` + 可选 `quote`（段落级） | 正文某段、某整节 |

| 模式 | 语义 | 适用 |
|---|---|---|
| `replace` | 用 `value` 覆盖锚点内容 | 改措辞、改数字口径 |
| `must_include` | 锚点内容/数组必须包含 `value`，缺失则补回 | 必须提到的关键事实 |
| `must_exclude` | 扫描范围内出现 `value` 即阻断 | 禁用表述、合规红线 |

**扫描范围**：`must_exclude` 检查该页 `card.l1`、`card.l2`、`card.fallback`、正文；不检查 `do_not_say` 列表本身与 `reason` 字段。

### 10.4 重编译校验算法

```text
输入：head_page, staged_page, active_pins
输出：patched_page, ledger[], blocked?

for pin in active_pins:
    head_anchor = resolve(pin.anchor, head_page)
    new_anchor  = resolve(pin.anchor, staged_page)

    if new_anchor is None and head_anchor is not None:
        new_anchor = fuzzy_reanchor(pin, staged_page)
        if new_anchor is None:
            ledger += orphaned(pin); blocked = true; continue
        pin.status = pending_confirmation; blocked = true   # 需人确认新位置
        ledger += reanchored_pending(pin)

    match pin.mode:
      replace:
        if value_at(new_anchor) != pin.value:
            write(pin.value, new_anchor); ledger += preserved(pin)
        else:
            ledger += noop(pin)
      must_include:
        if pin.value not in value_at(new_anchor):
            append(pin.value); ledger += preserved(pin)
      must_exclude:
        if pin.value in scan_scope(staged_page):
            ledger += violation(pin); blocked = true

apply confirmed pins → patched_page
```

**模糊重锚**：同 `heading` 下按文本相似度找最接近段落，阈值 0.8；命中只标记 `pending_confirmation`，**不自动视为成功**。人工确认后才改回 `active`。

### 10.5 结果码与处理

| 结果 | 含义 | 页面 | 是否阻断 |
|---|---|---|---|
| `preserved` | 编译器写错/漏写，Pin 覆盖成功 | 提交 | 否 |
| `noop` | 编译器输出与 Pin 一致 | 提交 | 否 |
| `reanchored_pending` | 原位置消失，模糊命中新位置 | 暂不提交 | ✅ 需人确认 |
| `orphaned` | 原位置与新位置都找不到 | 暂不提交 | ✅ 需人处理 |
| `violation` | 出现禁用表述 | 暂不提交 | ✅ |
| `retired` | 人工停用 Pin（保留历史） | — | 否 |

**阻断粒度是页，不是批次**。阻断页保持旧版本继续对外服务（但会 Lint `L006`/`L015`），不会把半成品发出去。

### 10.6 Pin、来源与冲突的优先级

```text
Pin（人工明确修正） > 新来源 > 旧页面
```

- 新来源与 Pin 冲突时：**文本保留 Pin**，同时创建 `CONFLICT`，页面置信度降红；不得用 Pin 把冲突"压掉"。
- 冲突裁决后若需要改 Pin 覆盖的文本，必须先 `retire` 旧 Pin，再写新值（留下审计链）。
- 同一字段最多 1 条 active `replace` Pin；多条必须报错，要求人合并。

### 10.7 Ledger 与"静默丢失"定义

每次提交写 `runs/<run_id>/pin-ledger.yaml`：

```yaml
run_id: run-20261025-02
pages:
  - page: qa:biggest-failure
    active_pins: 3
    checked: 3
    preserved: 2
    noop: 0
    reanchored_pending: 0
    orphaned: 0
    violation: 0
    created: 1
    retired: 0
```

- **静默丢失**：`head` 中存在、`commit` 后消失，且 ledger 中没有对应 `preserved/reanchored/orphaned/retired` 记录的内容变更。
- 目标值：**0**。提交前断言 `checked == active_pins`，否则拒绝提交。
- Pin 删除只能 `retired`，不得物理删除；`pins/` 进版本控制，历史可查。

### 10.8 反模式

| 反模式 | 后果 | 替代做法 |
|---|---|---|
| 把整页 Pin 住 | 页面永远不更新，等于冻结 | 只 Pin 必须稳定的那一句 |
| 用 Pin 掩盖冲突 | 冲突记录缺失，卡片假装可信 | 先建冲突，Pin 只保措辞 |
| 每次编辑都建 Pin | 维护成本爆炸，重编译频繁阻断 | 只 Pin"下次还会被改错"的内容 |
| Pin 派生字段（confidence） | 规则与展示不一致 | 改证据或改规则 |
| 直接手改 Markdown 文件 | 绕过审核与 Pin 记录 | 走 UI 编辑 |

### 10.9 人工编辑入口

| 入口 | 行为 |
|---|---|
| 审核页 `edit_then_approve` | 自动创建 Pin（`origin: review_edit`） |
| Wiki 页编辑保存 | 默认创建 Pin；用户可勾选"仅此版本"，则记录 `ephemeral_edit`，下次编译可能被覆盖（UI 必须明确警告） |
| 批量替换 | 禁止；只能逐页编辑 |

---

## 11. Conflict 契约

### 11.1 为什么绝不自动覆盖

自动选一个"看起来更新"的值，会让用户在面试现场说出一个自己都不知道对错的数据。**宁可显示"这里有两个口径"，也不要替用户下注。** 因此：

- 编译器只能创建冲突，`resolution` 只能由 `human:*` 写入；
- 未决冲突页置信度红，卡片必须给兜底话术；
- "冲突自动覆盖率"验收指标定义为 **0**，并在 CI 中断言。

### 11.2 检测器

| 检测器 | 触发 | 初始阈值 | 输出 kind |
|---|---|---|---|
| 数值比较 | 同 `metric.key`，`value_num` 差异 > 0.5% | — | `numeric_mismatch` |
| 口径比较 | 同 key、数值相近但 `scope/period` 不同 | — | `scope_mismatch` |
| 事实比对 | 同实体/同主题的 claim `statement` 语义相悖 | LLM 判定 + 人工抽检 | `factual_contradiction` |
| 时效 | 新来源 `valid_from` 晚于旧来源，且数值不同 | — | `temporal_supersede` |
| 身份 | 两个 entity 的 `aliases` 重叠 ≥1 且类型相同 | — | `identity_duplicate` |
| 重复页 | 标题+summary 3-gram Jaccard ≥0.6，LLM 确认同义 | 0.6 | `duplicate_page` |

### 11.3 记录格式

```yaml
schema_version: "1.0"
conflict_id: cfl-01JCF7P3T2M8N4R6W9Y1B5D7F3
status: open                  # open | resolved | dismissed
kind: numeric_mismatch
severity: major               # blocker | major | minor
detected_at: 2026-10-25T10:05:00+08:00
detected_by: rule:numeric     # rule:* | llm:* | human:*
run_id: run-20261025-02
subject:
  pages: [metric:availability-2025]
  key: availability
variants:
  - variant_id: v1
    value: "99.99%"
    evidence:
      source: source:resume-2026
      source_version: 1
      block: b-0005
      quote: "账务平台年度可用性 99.99%"
  - variant_id: v2
    value: "99.95%"
    evidence:
      source: source:postmortem-2025
      source_version: 1
      block: b-0006
      quote: "2025 年度可用性 99.95%，未达 99.99% 目标"
resolution:
  mode: null                  # null | choose | synthesize | scope_split | accept_both | dismiss
  chosen: null
  rationale: null
  resolved_by: null           # 必须是 human:*
  resolved_at: null
due_at: 2026-11-01
audit:
  - {at: 2026-10-25T10:05:00+08:00, by: compiler, action: created}
```

### 11.4 页面与卡片行为

| 对象 | 行为 |
|---|---|
| 冲突主体页 | `conflict_state: open`、`confidence.level: red`、正文顶部渲染"存在冲突"块 |
| 引用该页的 qa | 卡片红、`must_show_fallback_first: true`、显示冲突徽标 |
| 场景 Top 20 | 保留该问题，标记"待澄清"，会前准备页提示需先裁决 |
| 查询 | 可命中，但 L1 之后立即显示兜底；不允许只展示 L2 而隐藏冲突 |
| 导出/分享 | 冲突页禁止导出为"标准答案" |

### 11.5 解决流程

1. 人打开冲突，看到两个 variant 的原文、页码、上下文。
2. 选择模式：
   - `choose`：选一个 variant，另一个标为 `counter` 证据保留；
   - `synthesize`：写新的表述（通常"简历口径 99.99%，复盘口径 99.95%，对外用复盘值"），两个来源都保留；
   - `scope_split`：确认是两个不同口径，拆成两个 metric（key 加后缀）；
   - `accept_both`：仅在范围确实不同（如不同月份）时使用，必须填 scope；
   - `dismiss`：确认不是冲突（如统计口径不同），必须写理由。
3. 填写 `rationale`，签名 `human:<name>`，写 `resolved_at`。
4. 更新受影响页面（走正常编辑/Pin 流程），重算置信度。
5. 追加 `audit`；`status: resolved`；重新跑 Lint。

### 11.6 禁止

- 编译器写 `resolution`、`resolved_by`、`chosen`；
- 把 `dismiss` 当"懒得处理"；
- 用 Pin 覆盖冲突文本但不建冲突记录；
- 同一冲突重复创建（按 `subject.key + variant evidence` 去重）。

### 11.7 度量

| 指标 | 定义 | 目标 |
|---|---|---|
| 冲突自动覆盖率 | `resolution` 由非 `human:*` 写入的比例 | **0** |
| 检测召回 | 每周抽 30 页人工找冲突，与系统记录比对 | ≥80%（W7 起） |
| 平均未决时长 | `resolved_at - detected_at` | ≤5 天 |

---

## 12. Lint 契约

### 12.1 检查清单

| Code | 级别 | 检测 | 修复 | 门禁 |
|---|---|---|---|---|
| `L001` | blocker | `[[id]]` 目标不存在 | 建页或改链 | publish |
| `L002` | blocker | frontmatter 不符合 schema / 类型与目录不符 | 修字段 | publish |
| `L003` | blocker | 知识页 `evidence` 为空，或 qa `evidence_refs` 为空 | 补证据 | publish |
| `L004` | blocker | 卡片/正文数字无法在证据中找到 | 补来源或删数字 | publish |
| `L005` | blocker | 存在 open 冲突 | 裁决 | publish + prep（must_hit） |
| `L006` | blocker | Pin 孤儿或待确认 | 处理 Pin | publish |
| `L007` | major | 证据指向已归档/不存在的 source 版本或 block | 重新导入 / 更新证据 | publish |
| `L008` | major | 过 `review_after` 或 `valid_until` | 复核或更新 | — |
| `L009` | major | 页面语义重复（≥0.6） | 合并/删除其一 | — |
| `L010` | minor | 页面无入链且不在索引 | 挂索引或归档 | — |
| `L011` | major | 卡片超限（L1/L2 条数或长度） | 重生成卡片 | prep |
| `L012` | major | 场景 `must_hit` 问题没有 active qa | 建 qa | prep |
| `L013` | blocker | `card.built_from.revision` 与证据页当前 revision 不符 | 重生成卡片 | prep |
| `L014` | minor | 页面未出现在所属领域索引 | 更新索引 | — |
| `L015` | blocker | 触发 `must_exclude` 禁用表述 | 改写 | publish + ask |
| `L016` | info / major | source 解析警告（表格丢失、OCR 低置信） | 人工核对 | 视严重度 |

### 12.2 运行时机

| 时机 | 范围 | 是否阻断 |
|---|---|---|
| 每次 Ingest 的 S4 | 受影响页面 | 阻断该 op |
| 每次提交前 | 受影响页面 + Pin | 阻断该页 |
| publish 前 | 全库 | 阻断发布 |
| 每日 02:00 | 全库 | 只报告 |
| 会前准备（生成 Top 20 时） | 场景相关页 | 阻断"准备完成" |
| 查询时 | **不跑 Lint** | — |

### 12.3 报告格式

```yaml
schema_version: "1.0"
lint_run_id: lint-20261025-01
started_at: 2026-10-25T10:30:00+08:00
scope: all
summary: {blocker: 2, major: 0, info: 1, pages: 14}
gate:
  publish_allowed: false
  prep_allowed: false
  reasons: ["L005: 2 个未决冲突", "场景 must_hit 命中 L005"]
issues:
  - code: L005
    severity: blocker
    page: claim:zero-downtime-migration
    locator: "/conflict_state"
    message: "存在未决冲突 cfl-01JCF8Q4...，不得作为卡片证据"
    suggested_fix: "裁决冲突后重编译该页"
    status: open
```

### 12.4 门禁语义

| 门禁 | 允许条件 | 失败时行为 |
|---|---|---|
| `publish_allowed` | 无任何 blocker | 不发布新版本，继续用旧快照 |
| `prep_allowed`（单场景） | 该场景 `must_hit` 页面无 blocker、卡片未过期 | 会前页标红，禁止标记"已准备" |
| `ask_allowed`（单次查询） | 目标 qa 无 `L005/L013/L015` | 默认只展示兜底 + 原因；L2 折叠并标注"待核实"，不得默认展开 |

---

## 13. Query 契约（从问题到提词卡）

### 13.1 接口与事件

```http
POST /v1/ask
{
  "scenario_id": "scenario:yunqi-backend-lead",
  "question": "你最大的失败是什么",
  "trigger": "manual",          // manual | auto
  "client_ts": "2026-11-03T14:12:03+08:00"
}
```

响应使用 SSE，分四帧（生产环境）；`examples/query/*.json` 是 `done` 帧的完整快照。

| 帧 | 内容 | 目标时间 |
|---|---|---|
| `l1` | 3–5 个关键词 + 置信度色 + 是否需兜底 | ≤0.8s |
| `l2` | 3–5 条骨架 | ≤1.5s |
| `l3` | 展开正文 + 引用列表 | ≤3s |
| `done` | ask_id、hit_path、timings、notices | 随 l3 |

### 13.2 命中判定

**候选生成三条路并行：**

1. **场景索引**：`scenario.questions` 中该场景的问题，规范化后与 `question`/`question_variants` 比对；
2. **FTS5 检索**：对 `title + summary + question + question_variants + card.l1` 建虚拟表，BM25 排序；
3. **别名/标签**：`aliases`、`tags` 精确命中。

**打分（初始版）：**

```text
s = 4.0 * exact_variant      # 规范化后与某条 variant 完全一致
  + 2.0 * token_overlap      # 问句实词与 question 的重合率
  + 1.0 * bm25_norm          # 归一化到 0..1
  + 0.5 * scenario_priority  # 1/2/3 档 → 0.5/0.3/0.1
  + 0.3 * freshness          # 未过期 1，review_due 0.5，过期 0
  - 3.0 * open_conflict      # 目标页有未决冲突
```

**接受条件**：`s ≥ 4.0` 且与第二名差距 `≥ 1.0`；否则视为未命中，进入降级链。

> 阈值是**初始值**，不是拍脑袋的最终值。W5 用 ≥200 条真实问句标注"top1 是否可接受"，以命中率/F1 调参，并把最终阈值写回本节。

**规范化**：去掉标点、语气词、重复字符；数字统一阿拉伯数字；英文统一小写。ASR 同音错误不在规范化阶段处理（见 §17 问题 5）。

**重新评估向量库的条件**（任一满足，先加 cross-encoder 重排，不直接上向量库）：

- 连续 2 周目录命中率 <85%；
- ≥30% 的真实问句因"换个说法"落榜；
- 页面规模 >1000 页。

### 13.3 降级链

| 层级 | 条件 | 输出 | 置信度上限 | `degraded` |
|---|---|---|---|---|
| L0 精确命中 | `exact_variant` 或分数达标 | 缓存卡片原样 | 卡片原级别 | false |
| L1 变体适配 | 命中同一 qa，但问法差异大 | 同卡片 + 一句"按你的问法"改写开头（可选） | 卡片原级别 | false |
| L2 BM25 组装 | 无 qa 命中，但正文块相关 | LLM 基于命中的 3–5 个 block 现场组卡，只许引用块内内容 | yellow | true |
| L3 兜底卡 | 无任何相关证据 | 只给兜底话术 + "这个我没准备" | red | true |
| 离线 | 网络不可用 | 本地快照中的缓存卡片 | 原级别 | true |

**降级路径的硬约束**：L2 组装的每一句都必须能映射到命中 block；映射失败则丢弃该句；整卡映射失败则退到 L3。

### 13.4 延迟预算

| 步骤 | P50 | P95 | 备注 |
|---|---|---|---|
| 问句规范化 | 15ms | 30ms | 本地 |
| FTS5 查询 | 20ms | 50ms | 本地 SQLite |
| 卡片缓存读取 | 15ms | 40ms | 预热后内存/本地 |
| 引用解析 | 30ms | 80ms | 按 block 取 quote |
| 网络往返 | 150ms | 350ms | 同城；弱网另计 |
| **L1 合计** | **~230ms** | **~550ms** | 目标 800ms，留 30% 余量 |
| L2（同一缓存，仅渲染） | +40ms | +100ms | 目标 1500ms |
| L3（正文+引用+可选快照） | +200ms | +600ms | 目标 3000ms |

**提速手段（按优先级）**：会前预取整场卡片到本地 → SQLite 卡片缓存 → 引用预解析 → 连接复用/HTTP2 → 弱网降级到本地快照。**不允许**在 L1/L2 路径加 LLM 调用。

### 13.5 渲染规则

1. 先出 L1，再出 L2，L3 折叠；不要等齐再渲染。
2. **红卡先兜底**：`confidence.level: red` 时，第一屏显示 `fallback` + 冲突徽标，L2 需二次展开。
3. 黄卡正常显示 L2，但顶部有"待核实"标记；点按可看理由（中文解释，不显示 `reason_code`）。
4. 每条 L2 的引用以角标 `E1` 展示；点按展开 quote + 来源文档名 + 页码。
5. 反馈按钮固定四个：**有用 / 没用 / 用了兜底 / 需要修改**；点击不打断当前展示。
6. 不做自动滚动、不做自动朗读（P1）。

### 13.6 引用可追溯

- 每个 `citation` 必须能解析到 `source` 的对应版本与 block；解析失败 → 该条不展示，并记 `L007`。
- 展示格式：`《简历 2026》第 1 页 · "…原始 quote…"`。
- 卡片中每个数字在 UI 上都能长按查看出处；没有出处的数字不允许渲染（L004 已拦截）。
- 目标：可追溯率 **100%**，每周抽 50 张卡人工核对。

### 13.7 反馈事件

```json
{
  "event": "card_useful",
  "ask_id": "ask-01JCF9...",
  "qa": "qa:biggest-failure",
  "scenario_id": "scenario:yunqi-backend-lead",
  "at": "2026-11-03T14:12:20+08:00",
  "latency_ms": 610,
  "meta": {"card_confidence": "red", "fallback_used": false}
}
```

`event` 枚举：`ask_shown / card_useful / card_useless / fallback_used / card_edited / prep_completed`。

**指标定义**（与验收口径一致）：

- 提词卡采纳率 = `(card_useful + card_edited) / ask_shown`；
- 兜底使用率 = `fallback_used / ask_shown`（用于判断知识缺口）；
- 愿意继续用 = W8 问卷 + 两周内 ≥3 次真实会话。

### 13.8 超时与失败

| 场景 | 行为 |
|---|---|
| L1 超 800ms | 立即显示预置兜底（本地），后台继续取 L2 |
| L2 超 1.5s | 只保留 L1 + "展开中" |
| L3 超 3s | 保留 L1/L2，引用显示"加载中"，可重试 |
| ASR 不可用 | 切手动输入问句（不阻塞提词） |
| 后端 5xx | 用本地快照卡片；标记 `degraded` |
| 页面被阻断（L005/L013） | 默认展示兜底 + 原因；L2 折叠并标注冲突，不得默认展开 |

---

## 14. 版本与迁移

| 变更类型 | 例子 | 版本位 | 兼容性 |
|---|---|---|---|
| 加可选字段 | 新增 `story.stack` | minor | 旧页仍合法 |
| 加枚举值 | 新增 `intent: negotiation` | minor | 旧页仍合法 |
| 改字段语义 | `confidence` 规则调整 | minor + 全量重算 | 需重编译 |
| 删字段/改 ID 格式/改必填 | 重命名 `card.l2` | **major** | 旧页拒绝加载，必须迁移 |

- 加载器只接受 `schema_version` 主版本相同的页面；`meta/schema_version.yaml` 记录当前版本与支持范围。
- 迁移脚本：`migrations/<from>_to_<to>.py`，读取全部页面 → 转换 → 写 staging → 跑 Lint → 一次性提交；失败回滚。
- 迁移期间双读窗口 ≤2 周；旧版本快照保留在 `meta/snapshots/`。

---

## 15. 验收指标 → 机制映射

| 验收指标 | 目标 | 靠什么机制保证 | 在哪度量 |
|---|---|---|---|
| 编译后页面语义重复率 | ≤10% | 决策矩阵禁止重复建页；`L009` + 合并审核 | 每周 Lint 统计 `L009` 页数 / 总页数 |
| 人工修正静默丢失 | 0 | Pin 锚点 + ledger + 提交前断言 | `pin-ledger.yaml`，CI 单测 |
| 冲突自动覆盖率 | 0 | schema 强制 `resolved_by: human:*`；CI 断言 | 冲突表扫描 |
| 查询目录命中率 | ≥85% | 场景索引 + 问题变体 + 打分阈值 | `hit_path=index` / 全部 ask |
| BM25 兜底后总命中率 | ≥95% | FTS5 兜底 + L2 组装 | `hit_path in {index,bm25}` / 全部 ask |
| L1 首屏延迟 | ≤0.8s | 预编译卡片 + 本地缓存 + 热路径零 LLM | `timings_ms.l1` P95 |
| L2 骨架延迟 | ≤1.5s | 同缓存读取 | `timings_ms.l2` P95 |
| 完整 L3 | ≤3s | 引用预解析 + 快照 | `timings_ms.l3` P95 |
| 引用可追溯 | 100% | `L001/L003/L004/L007` 拦截 + 抽检 | 每周 50 张卡审计 |
| 幻觉抽检率 | ≤5% | 数字追溯 + 证据强制 + 红黄卡降级 | 每周 50 条陈述人工标注 |
| 内测用户愿意继续用 | ≥60% | 反馈闭环 + 复盘 | W8 问卷 + 会话频次 |
| 提词卡采纳率 | ≥50% | 兜底质量 + 卡片可读性 | 反馈事件 |

**领先指标（W4 起每周看）**：Pin 数量/页（过高说明生成质量差）、红卡占比（过高说明证据不足）、未决冲突时长、单文档编译成本。

---

## 16. 端到端示例走查

`examples/wiki/` 是一个可校验的最小 Wiki（面试场景：林舟 → 云栖科技 后端负责人）。按顺序看：

| 步 | 文件 | 看什么 |
|---|---|---|
| 1 | [`examples/wiki/sources/postmortem-2025.md`](../examples/wiki/sources/postmortem-2025.md) | source 页与 block 锚点、extraction 警告 |
| 2 | [`examples/wiki/runs/run-20261025-02/ops.json`](../examples/wiki/runs/run-20261025-02/ops.json) | 一次导入产出的 10 个操作（含 NOOP / NEEDS_HUMAN） |
| 3 | [`examples/wiki/runs/run-20261025-02/review.yaml`](../examples/wiki/runs/run-20261025-02/review.yaml) | 人工编辑 → 自动生成 Pin |
| 4 | [`examples/wiki/pages/qa/biggest-failure.md`](../examples/wiki/pages/qa/biggest-failure.md) | 红色卡片如何组织：兜底前置、诚实叙述 |
| 5 | [`examples/wiki/pins/qa__biggest-failure.yaml`](../examples/wiki/pins/qa__biggest-failure.yaml) | 三条 Pin：两条 replace、一条 must_exclude |
| 6 | [`examples/wiki/conflicts/cfl-01JCF8Q4R6T2W8Y4B6D2F8H1K3.yaml`](../examples/wiki/conflicts/cfl-01JCF8Q4R6T2W8Y4B6D2F8H1K3.yaml) | 事实冲突记录与未决状态 |
| 7 | [`examples/wiki/lint/lint-20261025-01.yaml`](../examples/wiki/lint/lint-20261025-01.yaml) | 门禁为什么是 false |
| 8 | [`examples/wiki/query/ask-biggest-failure.json`](../examples/wiki/query/ask-biggest-failure.json) | 红色卡片的最终响应与引用 |
| 9 | [`examples/wiki/query/ask-unmatched.json`](../examples/wiki/query/ask-unmatched.json) | 未命中时 BM25 兜底，不允许编造 |

走完这 9 步，应能回答：**同一个"最大失败"问题，系统如何既不让用户说假话，又能在 1 秒内给出一句能开口的话。**

---

## 17. 待拍板的问题（W1 前需要你确认）

| # | 问题 | 我的建议 | 影响 | 最晚 |
|---|---|---|---|---|
| 1 | 页面类型是否就定这 8 类？`term/concept` 是否独立成页？ | 先并入 `entity`（`entity_kind: concept`），出现 ≥10 个术语再拆 | 编译复杂度、索引层级 | W1 末 |
| 2 | L1/L2 存在 qa 的 frontmatter 里，是否可接受？ | 保留：查询零解析成本；YAML 体积实测后再评估 | 编辑体验、Git diff 噪声 | W4 |
| 3 | 绿色门槛是否过严（2 独立来源 + 人审）？ | 先严后松；W6 看绿色占比，目标 20–40% | 用户对"可信"的感知 | W6 |
| 4 | Pin 是否先只做 `field` 锚点，`section` 放 P1？ | 是；section 锚点复杂度高、收益低 | W4 工作量 | W2 |
| 5 | 预测问题由编译期还是会前单独 run 生成？ | 会前单独 run（可结合最新简历/JD），复用编译产物 | Top20 新鲜度 | W6 |
| 6 | 问题变体如何覆盖 ASR 同音/口语？ | W5 用真实 ASR 语料扩充，禁止 LLM 臆造变体 | 命中率 | W5 |
| 7 | 是否允许手工创建 qa 页？ | 允许，走同一 schema + 同一审核 | 用户自主性 | W1 |
| 8 | 多人协作/权限模型？ | MVP 单用户；`created_by` 已预留 | 后端鉴权 | W8 |
| 9 | 源文档 OCR 质量门槛？ | 置信度低于阈值拒绝编译并提示重传 | 编译质量 | W2 |
| 10 | 索引层级 root → domain → scenario 是否过深？ | 保持 ≤3 层；场景不做独立索引页 | 检索延迟 | W5 |
| 11 | 延迟口径：L1 按 0.8s 还是 1.5s？ | 按验收表的 0.8s（最严）；放宽到 1.5s 可简化缓存 | W6–W7 性能工作量 | W1 |

---

## 18. 附录

### A. Ingest 系统提示词（基线版）

```text
你是个人知识库编译器。你的唯一任务是把给定文档块编译成结构化 Wiki 页面草稿。

【输入】
- 文档元信息与 block 列表（每个 block 有 id、页码、原文）
- 已有页面的 id/title/summary/confidence（不是全文）
- 页面模板与本契约的字段约束

【输出】
严格 JSON，遵循 ingest-ops.schema.json。只输出 JSON，不要解释。

【允许的操作】
CREATE / UPDATE / LINK / NOOP / CONFLICT / NEEDS_HUMAN

【硬规则】
1. 只能使用给定 block；引用必须逐字，不得改写、拼接、翻译、补全。
2. 每个知识页至少 1 条 evidence（qa 用 evidence_refs）；每个数字必须来自 quote。
3. 不创建与已有页面语义重复的页；不确定时输出 NEEDS_HUMAN。
4. 不删除页面，不修改 id，不修改 source 页。
5. 遇到两个来源说法不一致：输出 CONFLICT，保留双方，绝不选择、绝不覆盖。
6. 除证据原文与冲突变体外，不写"行业领先""保证""零故障"等无证据或绝对化表述。
7. 页面长度、L1/L2 条数与字数遵守模板注释中的上限。
8. 低信任来源（trust=low）只能作为 supporting/counter，不能单独支撑页面。
9. 每个 op 必须写 reason（≤50 字），说明为什么改/建/不动。
10. 输出前自检：每个 quote 是否能在对应 block 中逐字找到？每个数字是否有出处？

【失败】
证据不足、需要业务判断、涉及敏感表述 → NEEDS_HUMAN，blocking=true，给出 2–3 个可选方案。
```

### B. 降级卡组装提示词（仅 L2 路径）

```text
你是提词卡组装器。根据命中的 3–5 个文档块，为问题生成一张应急提词卡。

规则：
1. 每一句都必须能对应到给定块中的原文；对应不上就删掉。
2. 不许引入块外的事实、数字、评价。
3. L1 3–5 个关键词；L2 3–5 条骨架，第一条是开口句；fallback 必须诚实。
4. 输出 JSON：{l1, l2, fallback, used_blocks: [block_id], unsupported: []}
5. 如果无法组成 2 条以上有依据的骨架，返回 {insufficient: true}。
```

### C. 枚举速查

| 枚举 | 值 |
|---|---|
| `type` | index / source / entity / claim / story / metric / qa / scenario |
| `status` | draft / active / stale / retired |
| `entity_kind` | person / org / product / project / concept |
| `claim_kind` | experience / capability / technical / commercial / customer / market |
| `story_kind` | project / incident / conflict / achievement |
| `intent` | factual / behavioral / technical / motivation / risk / commercial / hr / other |
| `scenario_kind` | interview / pitch / meeting |
| `confidence.level` | green / yellow / red |
| `trust` | high / medium / low |
| `evidence.role` | primary / supporting / counter |
| `pin.anchor.kind` | field / section |
| `pin.mode` | replace / must_include / must_exclude |
| `pin.status` | active / pending_confirmation / orphaned / retired |
| `conflict.kind` | numeric_mismatch / scope_mismatch / factual_contradiction / temporal_supersede / identity_duplicate / duplicate_page |
| `conflict.resolution.mode` | choose / synthesize / scope_split / accept_both / dismiss |

### D. W1 冻结检查清单

- [ ] 确认 8 类页面与粒度（§5）
- [ ] 确认 frontmatter 必填字段（§6.1）
- [ ] 确认置信度规则 `rule_v1`（§6.2）
- [ ] 确认 Pin 锚点范围（§10.3，建议先 field）
- [ ] 确认冲突 kinds 与解决模式（§11）
- [ ] 确认 Lint 门禁语义（§12.4）
- [ ] 确认查询降级链与打分初始值（§13.2–13.3）
- [ ] 用 5–10 份真实文档跑一次 Ingest，核对 §15 的重复率/引用率/成本
- [ ] 把本文件的 `schema_version` 写入 `meta/schema_version.yaml` 并打 tag `wiki-schema-v1.0`

