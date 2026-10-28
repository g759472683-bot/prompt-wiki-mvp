# GitHub 竞品扫描：LLM Wiki × 实时提词

> 扫描时间：2026-10-25 · 数据源：GitHub Search API / 仓库 README / 官方文档
> 口径：star 数为扫描时点；"类似"按**能力重叠**判断，不按名字。
> 结论只基于公开描述与文档；未读完全部源码，涉及"没有某功能"的判断都标了"未发现/未核实"。

---

## 0. 结论先行

1. **"LLM Wiki" 已经是一个公开的、病毒式传播的模式，不是蓝海。** Karpathy 2026 年 4 月提出后，半年内出现 20k+ star 的桌面应用、35k star 的腾讯知识平台、以及几十个同名编译器/技能仓库。
2. **实时面试/会议提词是另一个成熟品类。** 开源侧已有 3k star 的 Natively（Cluely 开源替代）、数百 star 的 Windows 隐形提词器，普遍具备实时 ASR + 本地 RAG + BYOK。
3. **两者的交集几乎为空。** 本次检索中，唯一同时出现"teleprompter + 本地知识库 + BM25"的仓库只有 0 star 的小项目；**"编译期预生成 L1/L2 卡片 + 引用 + Pin/冲突治理 + 手机端"** 没有发现直接对应物。
4. **但护城河很薄。** 组件全都有：编译（llmwiki/WeKnora）、检索（BM25/混合）、实时（Natively）、提词（一堆）。缺的是"把卡片在会前编译好、会中 1 秒内读出"的产品化，这可以被复制。
5. **真正的差异化不在"Wiki"，在"最后一公里"**：高 stakes 场景下的**可说性、证据、时延、人工权威**。名字叫"LLM Wiki"反而会被 20k star 的先发者淹没。

---

## 1. 检索方法

- GitHub Search API：`llm wiki`、`knowledge base compiler llm`、`interview copilot`、`interview rag resume`、`teleprompter ai`、`teleprompter knowledge base`。
- 每个查询取 star 前 8–10；再读关键仓库的文档（llmwiki 官方文档、WeKnora 官网）。
- 参考学术/社区讨论：Karpathy 原 gist、Zenodo 立场论文、arXiv 预注册对比、HN 讨论。
- 局限：star 受时间影响；部分仓库 README 因网络无法抓取，只能依据仓库描述与 topics，已在表中标注"未核实"。

---

## 2. 集群 A：LLM Wiki / 知识编译器

| 仓库 | Stars | 栈 | 它做什么 | 与我们的重叠 |
|---|---:|---|---|---|
| [Tencent/WeKnora](https://github.com/Tencent/WeKnora) | 35.4k | Go | 文档 → RAG + Agent + 自动 Wiki；Wiki 图谱、页面编辑、版本回滚、原文引用 | 知识编译 + 引用 + 回滚；企业级、重 |
| [nashsu/llm_wiki](https://github.com/nashsu/llm_wiki) | 21.0k | TypeScript | 跨平台桌面应用；文档增量编译成互链 Wiki，明确对标"传统 RAG 每次重查" | **最接近的消费级产品**；桌面、通用知识 |
| [TencentCloud/TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) | 29.9k | TypeScript | 团队级 Agent 记忆中枢，四种记忆资产之一是 "LLM-Wiki" | 把 Wiki 当记忆层；B 端 |
| [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) | 15.8k | Python | Obsidian + Claude Code 的自组织"第二大脑"，纯 Markdown 知识图谱 | 个人知识库 + Markdown；无实时场景 |
| [inkeep/open-knowledge](https://github.com/inkeep/open-knowledge) | 4.7k | TypeScript | 公司知识库/文档站，topics 含 llm-wiki-karpathy | 团队知识；非个人提词 |
| [SamurAIGPT/llm-wiki-agent](https://github.com/SamurAIGPT/llm-wiki-agent) | 3.7k | Python | 自维护个人 Wiki，Claude/Codex/Gemini 均可驱动，无 API key | 编译流程与我们相似 |
| [Astro-Han/karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) | 2.6k | Python | Agent Skills 版 LLM Wiki：原始资料 + 引用 + lint | **引用 + lint**，与我们最像的"规范派" |
| [atomicstrata/llm-wiki-compiler](https://github.com/atomicstrata/llm-wiki-compiler) | 2.2k | TypeScript | "知识编译器"：类型化页面、段落/claim 级引用、review 队列、lint/eval、MCP、增量状态 | **能力最完整的开源编译器**，建议直接试用 |
| [coleam00/claude-memory-compiler](https://github.com/coleam00/claude-memory-compiler) | 1.3k | Python | 把 Claude Code 会话编译成跨引用知识文章 | 编译流水线参考 |
| [xoai/sage-wiki](https://github.com/xoai/sage-wiki) | 637 | Go | 单二进制、个人→团队→公司的图谱 Wiki | 部署形态参考 |
| [arturseo-geo/llm-knowledge-base](https://github.com/arturseo-geo/llm-knowledge-base) | 40 | Markdown | 纯 **schema 标准**：AGENTS.md 规范、模板、完整示例、间隔复习层 | 与你的"契约文件"同一生态位 |
| [bybit-exchange/kaas](https://github.com/bybit-exchange/kaas) | — | — | 笔记/文档/转写 → 可查询 Markdown Wiki；**无 embedding**、自托管、MCP | "不上向量库"的同路人 |

**这个集群说明什么**：编译、类型化、引用、lint、review 都已经被开源实现过，而且做得不浅。llmwiki 甚至已经有 `contradictedBy`、`provenanceState`、低置信度自动 hold、claim 级行号引用、`query --save` 把答案回写 Wiki。

---

## 3. 集群 B：实时面试 / 会议 Copilot

| 仓库 | Stars | 栈 | 它做什么 | 关键差异 |
|---|---:|---|---|---|
| [Natively-AI-assistant/natively-cluely-ai-assistant](https://github.com/Natively-AI-assistant/natively-cluely-ai-assistant) | 3.1k | TypeScript | 开源 Cluely 替代：实时转写、会议纪要、本地 RAG、BYOK、stealth mode | 桌面端、实时生成答案；无"预编译卡片" |
| [JWM0203/MeetingCopilot](https://github.com/JWM0203/MeetingCopilot) | 361 | TypeScript | Windows 隐形会议/面试助手：本地 FunASR/云 ASR + **第一人称提词器答案**，屏幕共享不可见 | 形态最接近"提词"，但答案即时生成 |
| [iskandaryv/meetingly-ai](https://github.com/iskandaryv/meetingly-ai) | 324 | TypeScript | Zoom/Meet/Teams 实时答案，本地转写，屏幕共享隐藏 | 通用会议，非个人知识库 |
| [iam-epiphany/resume-agent](https://github.com/iam-epiphany/resume-agent) | 31 | Python | 简历 RAG 问答 Agent：第一人称作答；硬事实必须来自检索；证据不足强制标注"推测"；置信度分级、检索兜底链 | **"证据纪律"最接近我们的思路**，但是网页问答不是实时提词 |
| [Gamingpro237/Advanced_Interview_responder_with_AI](https://github.com/Gamingpro237/Advanced_Interview_responder_with_AI) | 13 | Python | 简历 + 实时转写问题 → teleprompter 显示答案 | 早期原型 |
| [Asalio123/suflyor-ai](https://github.com/Asalio123/suflyor-ai) | 0 | JavaScript | 实时会议提词 + 面试 copilot；**BM25 本地知识库**、流式 LLM、防抖自读 | 组合最像，但基本无人维护 |

**这个集群说明什么**：实时链路（ASR、悬浮窗、BYOK、低延迟）已经商品化；但公开实现几乎都是**现场生成**，没有"会前编译好的答案卡 + 可追溯引用 + 人工修正存活"这套治理。它们优化的是"说得像"，我们优化的是"说得对、说得出"。

---

## 4. 集群 C：纯提词器

[promptme-ai](https://github.com/larsbaunwall/promptme-ai)（32★，浏览器 AI 提词）、[CueRecord](https://github.com/nolangz/CueRecord)（65★，macOS 录屏+提词）、[PromptDeck](https://github.com/waynesutton/teleprompter)（5★，脚本+提词）。这类只解决"读"，不解决"答什么"，与我们的知识层不冲突，可作为 Android 提词 UI 的交互参考。

---

## 5. 能力对照（只填能核实的）

| 能力 | 我们（契约 v1.0） | llmwiki-compiler | WeKnora | Natively / MeetingCopilot | nashsu/llm_wiki |
|---|---|---|---|---|---|
| 文档 → 互链 Wiki | ✅ | ✅ | ✅ | ❌（RAG） | ✅ |
| 类型化页面 + schema | ✅ 8 类 | ✅ 4 类 + schema.json | ◐ 实体/概念 | ❌ | 未核实 |
| 段落/claim 级引用 | ✅ block + 逐字 quote | ✅ 行号范围 | ✅ 原文定位 | ◐ 答案引用 | 未核实 |
| 人工审核队列 | ◐ 有 review.yaml，无 UI | ✅ review/hold | ◐ 编辑/回滚 | ❌ | 未核实 |
| 冲突记录（不自动裁决） | ✅ 6 种 kind | ◐ `contradictedBy` + hold | 未发现 | ❌ | 未核实 |
| 人工修正重编译存活（Pin） | ✅ 锚点 + ledger | ❌（候选页保留旧版） | ❌ | ❌ | 未核实 |
| **预编译 L1/L2 提词卡** | ✅ | ❌ | ❌ | ❌（现场生成） | ❌ |
| 实时 ASR | P0 手动，P1 自动 | ❌ | ❌ | ✅ | ❌ |
| 手机端（Android） | ✅ | ❌（CLI/桌面） | ◐ Web | ❌（桌面） | ❌（桌面） |
| 时延预算/降级链 | ✅ | ❌ | ❌ | ◐ 工程实现 | 未核实 |
| 不上向量库 | ✅ BM25/FTS5 | ◐ 可选语义检索 | ❌ 混合检索 | ◐ 本地 RAG | 未核实 |

> 说明：`—` 表示未查到公开信息；`◐` 表示部分具备。对 nashsu/WeKnora 的"未核实"不是"没有"。

---

## 6. 学术与社区信号：LLM Wiki 不是万能药

- **Zenodo 立场论文（2026-05）**：把 LLM Wiki 视为"编译后的语义记忆"，不是 RAG 的替代；作者报告该模式**在两个测试领域没有跑赢 RAG**，且当前形态受"个人知识库规模"限制。
  <https://zenodo.org/records/20078453>
- **arXiv 预注册对比（2026）**：在 24 篇论文 / 13 个问题上，Wiki 在**跨论文综合**上大幅领先，RAG 在**单点事实 groundedness** 上更好；但 Wiki 的**单次查询 token 约为 RAG 的 21 倍**（agent 逐页浏览、未开缓存），"编译一次、查询更便宜"的假设被推翻。claim 级引用支持度 Wiki 更好。
  <https://ar5iv.labs.arxiv.org/html/2605.18490>
- **对我们的直接含义**：这两篇正好替我们证明了"**查询热路径不能靠 agent 浏览 Wiki**"。我们把 L1/L2 预编译进 qa 页面，查询只读缓存，恰好绕开了 21× 成本和延迟问题。这是我们相对"通用 LLM Wiki"的工程优势，应写进 PRD。

---

## 7. 我们真正剩下的差异点

### 7.1 真差异（值得押注）

1. **会前预编译的"可说卡片"**：不是知识页，也不是现场生成答案；是 3–5 个关键词 + 3–5 句骨架 + 兜底，按 0.8s/1.5s/3s 分层出。
2. **证据 + 冲突 + Pin 的现场治理**：说出口的每句话可追溯；有冲突就红卡先兜底；人工改过的措辞重编译不丢。现有竞品没有把这套带进"说话"路径。
3. **手机 + 蓝牙的形态**：不装对方电脑、不碰屏幕共享；面试/路演/线下会议都能用。桌面 stealth 品类解决的是线上会议，不是这个场景。

### 7.2 伪差异（别当卖点）

- "用 LLM 维护 Wiki" —— 20k star 应用已经在做，且开源。
- "不上向量库" —— 有 bybit/kaas 等同类，且只是实现选择，用户不感知。
- "引用可追溯" —— llmwiki、WeKnora 都有；我们只是把它做到卡片层。
- "本地优先/隐私" —— Natively、MeetingCopilot 也在讲。
- "更多页面/更强模型" —— 不是这个产品的战场。

---

## 8. 应该抄的 7 个设计

| # | 来源 | 抄什么 | 怎么落到我们的契约 |
|---|---|---|---|
| 1 | llmwiki | `contradictedBy` / `provenanceState` 字段 | 我们的 `conflicts` / `conflict_state` 已覆盖，补一个 `provenance_state: merged/derived/verbatim` |
| 2 | llmwiki | review hold 模式（low-confidence / contradicted / schema-violating / provenance-violating） | 直接把 Lint 门禁的原因码对齐这四类，UI 文案可复用 |
| 3 | llmwiki | claim 级行号引用 | 我们用 `block + quote + chars`，对 PDF/中文更稳；保留差异，但补"行号/字符区间"展示 |
| 4 | llmwiki | `query --save`：把好答案回写成 Wiki 页 | 战后复盘：把用户编辑过的卡片沉淀为新的 qa/claim，形成飞轮 |
| 5 | llmwiki | 按 source sha256 的增量状态 | 我们已有 `source.sha256 + version`，补 `state.json` 只重编译变更文档 |
| 6 | WeKnora | Wiki 图谱 + 版本回滚 + 原文定位 UI | 审核页三件套：diff、来源跳转、回滚；W2–W3 直接照这个做 |
| 7 | Natively / MeetingCopilot | 本地 ASR、BYOK、悬浮提词交互 | Android 端做"锁屏/悬浮卡 + 耳机键触发"，不做 stealth |

---

## 9. 不该做的 4 件事

1. **不要再从零造通用 Wiki 编译器**。先用 llmwiki-compiler / nashsu / kaas 跑 5–10 份文档，做质量基线；再决定"复用 + 改造"还是"自研"。
2. **不要叫"LLM Wiki"**。品类名已被 20k star 项目占据，且用户听不懂。对外说"面试/路演的作战卡"或"个人简报编译器"。
3. **不要做桌面端隐形悬浮窗**。红海、平台对抗、道德争议；手机形态反而是差异。
4. **不要在查询热路径调 LLM**。学术对比已经给出 21× 成本的教训；我们的预编译路线要守住。

---

## 10. 风险：品类名声与合规

- 面试 copilot 在 GitHub 上直接带 `cheating`、`stealth`、`invisible to screen sharing` 标签；商业侧 Cluely/Final Round AI 争议很大。
- 如果主打"面试作弊"，会同时遇到：应用商店审核、面试方 ToS、雇主反感、品牌天花板。
- **建议**：技术上服务"高 stakes 对话"，首发场景选**路演/销售/媒体沟通/晋升答辩**这类"允许带资料"的场合；面试作为内部 dogfood，不作为对外主叙事。至少要在 PRD 里明确这条边界，W8 前定。

---

## 11. 对 8 周计划的具体修改

| 周 | 原计划 | 建议调整 |
|---|---|---|
| W1 | 写 PRD + 冻结 Schema | 加一项：用 llmwiki-compiler / nashsu 跑 5 份真实文档，产出对比基线；决定 build vs reuse |
| W2–W3 | Ingest 流水线 v1 | 若 reuse：只做适配层 + 审核 UI；若 build：直接抄 review-policy / 增量 state / 引用格式 |
| W4 | Pin + 冲突 | 不变，这是我们相对开源编译器的差异，别砍 |
| W5 | Query + BM25 兜底 | 不变；把"预编译卡片绕开 21× 查询成本"写进技术叙事 |
| W6 | Top20 + 蓝牙 | 不变；把 Android 形态作为差异点验证（锁屏卡、耳机键、弱网） |
| W7 | Lint + 反馈 + 性能 | 补"hold 原因码"与"红卡兜底率"看板 |
| W8 | 内测 | 首发场景建议避开"面试"对外叙事，先找 3–5 个路演/销售场景用户 |

---

## 12. 参考链接

- Karpathy 原 gist（LLM Wiki 模式）：<https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- llmwiki 官方文档（页面类型/引用/review policy）：<https://llmwiki.atomicstrata.ai/introduction>
- WeKnora 官网（自动 Wiki / 图谱 / 回滚 / 引用）：<https://weknora.weixin.qq.com>
- Zenodo 立场论文：<https://zenodo.org/records/20078453>
- arXiv 预注册对比：<https://ar5iv.labs.arxiv.org/html/2605.18490>
- 仓库列表见 §2/§3 表格内链接。

---

## 13. 一句话

> **这个方向不是没人做，而是"上游"已经很挤、"最后一公里"还没人认真做。**
> 把 8 周从"造 Wiki"改成"造卡片 + 造证据治理 + 造手机端时延"，胜率会高很多。
