# Backend（v0.2）

范围：**认证/工作区 + 上传 + 解析 + 引用校验 + DeepSeek 页面/卡片编译 + job worker + 审核/发布 + `/v1/ask` 混合召回 + 跨文档一致性 + 论点 Pin + 置信度校准 + Web 后台 + APK 发布**。
不含：story/entity、多文档场景 prep、云端 ASR（后续）。

## 1. 本地启动

要求 Python 3.11+。

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements-dev.txt
# 国内网络可用镜像：
# pip install -r requirements-dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

$env:SECRET_KEY = "dev-only-change-me-0123456789abcdef"
$env:INVITE_CODES = "W1-DEMO"
$env:DATA_DIR = "./data"
$env:DEEPSEEK_API_KEY = "sk-..."   # 服务端专用，不要提交

uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000

# 另开一个终端处理异步编译任务
python -m app.worker
```

- OpenAPI：<http://127.0.0.1:8000/docs>
- Web 运营台：<http://127.0.0.1:8000/admin>
- 同一邀请码 = 同一工作区；手机和 Web 共享文档/卡包。
- APK 发布：`POST /v1/releases` → `POST /v1/releases/{id}/activate` → `GET /v1/app/latest`。

Docker：

```bash
cp .env.example .env
docker compose up --build
```

## 2. 一条完整的手工冒烟

```bash
# 1) 换 token
curl -s -X POST http://127.0.0.1:8000/v1/auth/device \
  -H "Content-Type: application/json" \
  -d '{"device_id":"dev-demo-0001","invite_code":"W1-DEMO"}'

# 2) 上传
curl -s -X POST http://127.0.0.1:8000/v1/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./resume.pdf" \
  -F "doc_type=resume" \
  -F "trust=high"

# 3) 看 block
curl -s http://127.0.0.1:8000/v1/documents/$DOC_ID/blocks \
  -H "Authorization: Bearer $TOKEN"

# 4) 校验一句引用是否逐字命中
curl -s -X POST http://127.0.0.1:8000/v1/documents/$DOC_ID/quote \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"block_id":"b-0001","quote":"在这里放原文里的一句话"}'

# 5) 用 DeepSeek 编译页面 + 10–15 张卡（同步，两次调用，约 40–90s）
curl -s -X POST http://127.0.0.1:8000/v1/documents/$DOC_ID/compile \
  -H "Authorization: Bearer $TOKEN"
```

编译结果写到 `wiki/.staging/<run_id>/pages/`（claim/metric/qa）与 `pack.json`，同时生成 `wiki/runs/<run_id>/manifest.yaml`。返回 `pages`、`cards`、`run_id`、token 数与耗时。只编译页面可加 `?with_cards=false`。

产品路径用**异步 job**（同步接口只用于调试）：

```bash
# 入队
curl -s -X POST http://127.0.0.1:8000/v1/compile-jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_id":"'$DOC_ID'","with_cards":true}'

# 另开一个终端跑 worker（--once 处理一个就退出）
python -m app.worker

# 查 job
curl -s http://127.0.0.1:8000/v1/jobs/$JOB_ID -H "Authorization: Bearer $TOKEN"

# 看 staging、批准发布
curl -s http://127.0.0.1:8000/v1/runs/$RUN_ID/review -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://127.0.0.1:8000/v1/runs/$RUN_ID/approve -H "Authorization: Bearer $TOKEN"
```

PowerShell 用 `Invoke-RestMethod`；上传用 `-Form @{ file = Get-Item .\resume.pdf; doc_type = "resume"; trust = "high" }`。

## 3. 接口（D1–D5）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | 存活 |
| POST | `/v1/auth/device` | 邀请码 + device_id 换 JWT |
| POST | `/v1/documents` | multipart：`file`、`doc_type`、`trust` |
| GET | `/v1/documents` | 我的文档列表 |
| GET | `/v1/documents/{id}` | 详情（状态/来源/block 数） |
| DELETE | `/v1/documents/{id}` | 软删 |
| GET | `/v1/documents/{id}/blocks` | block 列表 |
| GET | `/v1/documents/{id}/blocks/{block_id}` | 单个 block |
| POST | `/v1/documents/{id}/quote` | 校验 quote 是否命中（exact/normalized） |
| GET | `/v1/sources/{source_id}/blocks/{block_id}` | 引用弹层用 |
| POST | `/v1/documents/{id}/compile` | 同步编译（调试用）；产品走下面的 job |
| POST | `/v1/compile-jobs` | 入队异步编译：`{document_id, with_cards}` |
| GET | `/v1/jobs` | 我的 job 列表 |
| GET | `/v1/jobs/{id}` | job 状态/结果 |
| GET | `/v1/runs/{run_id}/review` | staging 审核视图（页面/卡片/冲突/警告） |
| POST | `/v1/runs/{run_id}/approve` | 批准：页面写正式 Wiki，pack 写 `packs/` |

错误码：`401` 无/坏 token，`403` 邀请码错，`404` 非本人或不存在，`413` 超限，`415` 类型不支持，`422` 参数/空文件/无可用页面，`409` 全部页面已存在，`502` LLM 失败，`503` 未配置 `DEEPSEEK_API_KEY`。

## 4. 落盘结构

```text
data/
├── app.db
└── users/<uid>/
    ├── uploads/<doc-id>.pdf
    └── wiki/
        ├── sources/<doc-id>.md              # 符合 Wiki Schema v1.0 的 source 页
        ├── .staging/<run-id>/pages/         # 编译草稿（未审核）
        ├── .staging/<run-id>/pack.json      # staging 卡包
        ├── pages/{claim,metric,qa}/         # 批准后的正式页面
        ├── packs/<pack-id>.json             # 批准后的卡包
        └── runs/<run-id>/{manifest,review}.yaml
```

source 页示例：

```markdown
---
schema_version: '1.0'
id: source:doc-0123456789ab
type: source
...
---

# 林舟简历

<!-- b-0001 | p.1 | chars:0-38 -->
林舟｜后端工程师｜8 年经验
```

## 5. 已知边界（D1–D5 故意不做）

- 同步 `/compile` 仍保留给调试；产品路径是 `compile-jobs` + worker。worker 目前单进程、无重试/优先级。
- 页面类型只做了 `claim` / `metric` / `qa`；`story` / `entity` 还没做。
- 审核/批准是**后端 + 文件**，还没有 UI；批准会跳过已存在的页面并返回 collisions，不做自动合并。
- 没有 Pin、冲突裁决、Lint 门禁；批准前只做基础字段检查。
- 没有场景 `prep`：卡是按文档生成的，不是按"一场对话"组装的。
- PDF 只支持文本层；扫描件直接报错，不自动 OCR。
- 认证是"邀请码 + device_id"，不是强账号体系；内测够用，上线前要换。
- 没有限流、审计、清理任务；删除是软删。
- 本地验证：**25 个测试通过**（含 PDF/DOCX、引用、schema、页面/卡片、job、审核/批准）。
- 五文档基线：每份 6 blocks → 4–6 页 + **12–15 张卡**；42–93s；8k–19k output tokens；schema 0 失败；仅 1 张卡因数字无法追溯被丢弃。
- 真实异步 E2E：入队 → worker → 5 页 + 12 卡 → 审核 17 页 → 批准 17 页 + pack，0 collision。
- `python-docx` / `pdfplumber` 的解析结果依赖版式；真实文档若表格/分栏严重，先看 `extraction.warnings`。

## 6. 测试

```bash
cd backend
pytest -q
```

覆盖：邀请码、token、上传 TXT、source 页 frontmatter、block 数、逐字/空白归一化引用、重复上传、用户隔离、非法类型、空文件、删除后重传、PDF/DOCX 解析、source/claim/metric/qa schema 校验、页面编译、卡片生成、数字追溯、L1/L2 兜底修复、job 入队/执行/失败、审核/批准/collision、DeepSeek client 成功/认证失败。

五文档基线：

```bash
python scripts/baseline.py
# 输出 data/baseline/report.md
```

离线校验生成页面：

```bash
python scripts/validate_pages.py data/users/usr-smoke/wiki/.staging/run-20261025-01/pages
```

## 7. 下一步（D6）

1. 场景 `prep`：从多份文档的卡里选 20 张，生成场景卡包（现在卡是文档级）。
2. `story` / `entity` 页面：补 STAR 与公司/项目实体。
3. Pin / 冲突 / Lint 门禁：批准前做完整校验。
4. 审核台 UI（当前只有后端接口）。
5. Android 壳 + 卡包预载（D7）。
