# Run run-20261025-02 审核差异

**输入**：`账务平台-20250918-P1-复盘.docx`（6 个 block，1 条解析警告）
**模型**：deepseek-v3.1 · prompt ingest-1.0.0 · temperature 0
**成本**：48,210 in / 6,210 out / $0.038 · 51.2s

## 摘要

| op | 动作 | 对象 | 置信度变化 |
|---|---|---|---|
| op-01 | UPDATE | claim:ledger-migration-led | 绿 → 绿（证据 +1） |
| op-02 | CREATE | story:ledger-migration-2025 | — → 黄（disputed_evidence） |
| op-03 | CREATE | qa:biggest-failure | — → 红（open_conflict） |
| op-04 | LINK | qa:biggest-failure → scenario | 场景新增必答卡 |
| op-05 | CONFLICT | metric:availability-2025 | 红（未决） |
| op-06 | CONFLICT | claim:zero-downtime-migration | 红（未决） |
| op-07 | NOOP | entity:yunqi-tech | 无变化 |
| op-08 | NEEDS_HUMAN | availability 口径 | 阻塞"完成" |
| op-09 | UPDATE | qa:why-this-role | 绿（仅刷新 built_from） |
| op-10 | UPDATE | qa:migration-architecture | 绿（仅刷新 built_from） |

## op-01 claim 证据追加

```diff
 evidence:
   - source: source:resume-2026
     block: b-0004
     role: primary
+  - source: source:postmortem-2025
+    block: b-0005
+    quote: "迁移由林舟牵头，架构方案无问题"
+    role: supporting
+    verified: true
```

两份独立来源，规则重算仍为绿色。

## op-03 卡片：编译器草稿 → 人工修改

| 位置 | 编译器草稿 | 人工修改 | 结果 |
|---|---|---|---|
| `/card/l2/0` | 2025 年迁移时出过一次 P1，很快就恢复了 | 2025-09 迁移当晚 P1，延迟 4 小时 12 分 | ✅ 生成 Pin `pin-01JCF7R2...` |
| `/card/fallback` | 这块我记不清了，回头查一下。 | 这次事故我有责任，具体数字我按复盘口径说，不粉饰。 | ✅ 生成 Pin `pin-01JCF7S4...` |
| `/body` | （无禁用词） | 追加规则：禁止"零故障" | ✅ 生成 Pin `pin-01JCF8A3...` |

**Pin 影响**：3 条均作用于本页，无跨页覆盖；重编译时按 §10.4 校验。

## op-05 / op-06 冲突

- `cfl-01JCF7P3...`：99.99%（简历）vs 99.95%（复盘），`numeric_mismatch`，未决。
- `cfl-01JCF8Q4...`：迁移零故障（简历）vs P1 三小时五十五分（复盘），`factual_contradiction`，未决。
- 两者都**没有**写 `resolution`；页面置信度降红，卡片强制兜底。

## 数字追溯（抽样）

| 数字 | 位置 | 证据 |
|---|---|---|
| 4 小时 12 分 | card.l2[0] | postmortem b-0002 |
| 12 个服务 / 2.3 亿笔 | card.l2[1..3] | resume b-0004 |
| 45 分钟 / 8 分钟 | card.l2[3] | resume b-0005 |

## 门禁

- `publish_allowed: false`（2 个未决冲突）
- `prep_allowed: false`（必答卡为红色，且场景在新增卡片后未重新准备）
- `ask_allowed(qa:biggest-failure): false` → 默认兜底 + 冲突提示，L2 折叠待展开
