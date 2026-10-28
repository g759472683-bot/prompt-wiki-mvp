# Android v0.6.0

> 状态：v0.1 已在 Redmi K80 真机跑通；**v0.6.0 已构建**：1–4 条摘要可点开论证详情 + 追问预案 + 逐条置信度；支持论点 Pin、跨文档冲突提示、实测置信度、无依据 LLM 开关、**离线中文语音（Vosk 小模型）**。
> v0.2 新增：批量导入、混合召回兜底、Web 后台、APK 发布。

## 1. 下载 / 安装

手机和电脑同一 Wi-Fi（当前是电脑热点），手机浏览器打开：

```text
http://192.168.137.1:8080/app-debug.apk
```

- 大小约 **65MB**（含 42MB Vosk 中文模型和 native 库），debug 签名；需允许浏览器"安装未知应用"。
- 只打包 `arm64-v8a`，Redmi K80 可用；覆盖安装会保留登录和本地卡包。
- USB 安装：

```powershell
C:\Android\sdk\platform-tools\adb.exe install -r dist\promptwiki-0.6.0.apk
```

APK 副本：[`dist/promptwiki-0.6.0.apk`](dist/promptwiki-0.6.0.apk)

## 2. 后端（两个进程）

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

另开一个终端：

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m app.worker
```

- App 后端地址：`http://192.168.137.1:8000`
- Web 后台：`http://192.168.137.1:8000/admin`
- 邀请码：`W1-DEMO`（邀请码 = 工作区，手机和 Web 同邀请码共享数据）

## 3. App 流程

1. 登录（地址、邀请码 `W1-DEMO`、名字）。
2. 首页先选：**进入已有卡包**，或**上传新资料**；本地没有时会自动从服务器找最近发布的 pack。
3. 一次选 **1–5 份** PDF/Word/TXT/MD。
4. 每份跑一个 job；全部完成后合并成一个卡包（最多 20 张）。
5. 看到"N 个来源 · 页面 X · 卡 Y" → **批准全部并开始**。
6. 现场页：大按钮 / 蓝牙媒体键触发；L1/L2/L3；引用弹层；红卡兜底在前。
7. **点 L2 的 1–4 条**：底部弹出该论点的详细说法、技术/架构/流程说明、可能追问 Q&A、依据和该条置信度。
8. 论点详情里点 **“编辑并固定这条”**：改摘要/展开，保存后成为 Pin；重新编译不会被覆盖。
9. 首页会显示跨文档检查摘要（高危/中危）；Web 后台“一致性”看详情。
10. 设置页可开 **“无依据也允许 LLM 回答”**：没召回原文时仍回答，但卡片标红并提示“无原文依据，可能不可靠”；默认关闭。
11. 本地没命中时，自动调 `/v1/ask`：BM25 召回原文块 → LLM 现场组装带引用的回答（约 3–6s，标“现场组装”）。
12. **离线语音**：点“开始离线语音”，首次会加载模型（几秒），之后连续听；partial 实时进输入框，停顿出 final。
13. 听不到/识别不准时，仍可用输入框或搜狗/Gboard 麦克风兜底。
14. 卡包缓存在本地；设置页可“检查更新”。

## 4. Web 后台

打开 `http://192.168.137.1:8000/admin`：

- 文档：批量上传、看状态、逐份编译。
- 任务 / 审核：轮询进度；`succeeded` 后审核并批准。
- 卡包：看已发布 pack、每张卡、逐条 points；可编辑并固定论点。
- 一致性：跨文档 metric/claim 冲突扫描。
- 校准：按置信档统计现场反馈的实测准确率。
- APK 发布：上传 APK、填 versionCode/versionName、点"发布"；App 通过 `/v1/app/latest` 检查。
- 双端互通：同一邀请码即同一工作区。

> Web 后台目前是**单用户工作区**，任何拿到邀请码的人都能管理；内测再收紧。

## 5. 构建

Vosk 模型（42MB）不进 Git，首次构建前拉取：

```powershell
cd android
.\scripts\fetch-vosk-model.ps1
```

然后：

```powershell
$env:JAVA_HOME="C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"
$env:ANDROID_HOME="C:\Android\sdk"
$env:Path="$env:JAVA_HOME\bin;$env:ANDROID_HOME\platform-tools;$env:Path"
C:\Gradle\gradle-8.9\bin\gradle.bat -p . assembleDebug --no-daemon
```

输出：`app/build/outputs/apk/debug/app-debug.apk`。
工具链：JDK 17.0.20 · SDK 35 / Build-Tools 35.0.0 · Gradle 8.9 · AGP 8.7.3 · Kotlin 2.0.21。

## 6. 已知边界

- 批量导入是**本地合并**卡片；后端仍是"一个文档一个 pack"，场景 prep 还没做。
- "批准"是全量批准；逐张编辑/Pin/冲突 UI 还没做。
- 置信度是**分档经验校准**：每档至少 5 条现场反馈后，pack 的 score 换成实测准确率，App 显示“实测”；否则显示“规则 60%”。不是模型概率。
- 跨文档一致性是**规则扫描**（同 metric key / 同 claim 标题），语义相同但标题不同的可能漏报；只提示，不自动改卡。
- 旧卡包没有 `points` 字段，App 会用 L2 行自动合成详情；启动时会检测并尝试从服务器刷新为展开版。当前服务器最新的 `pack-20261025-06` 已是展开版（12 张卡）。
- 重新编译同名资料会命中已有页面；Review 页会出现"覆盖旧页面并批准"，覆盖后旧 pack 仍保留在 Web 后台。
- 语音是**离线 Vosk 小中文模型**：42MB，WER 约 23.5（SpeechIO-02），专有名词/数字可能错；准确率不够时换 sherpa 或大模型。
- 首次启动会把模型从 assets 复制到 `externalFilesDir`，约几秒；之后离线可用。
- `/v1/ask` 是兜底，不是每次查询都走 RAG；延迟 3–6s。
- 蓝牙媒体键 best effort；没有锁屏提词、自动问题检测、TTS、iOS、眼镜。
- Web 后台无多用户权限；APK 只能提示下载，Android 不允许静默安装。

## 7. 排错

| 现象 | 处理 |
|---|---|
| 连不上/登录失败 | 地址用 `192.168.137.1`（热点网段），不是 `192.168.1.2`；防火墙放行 8000 |
| 一直 queued | worker 没启动：`python -m app.worker` |
| 生成失败 | 看 `/v1/jobs/{id}` 的 error；确认 `.env` 有 `DEEPSEEK_API_KEY` |
| 批准 409 | 页面已存在；换文档或清数据 |
| 语音不可用 | 点输入框，用键盘麦克风；云端 ASR 待接 |
| 更新检查 404 | Web 后台还没有"已发布"的 APK |
| 安装被拦 | 允许未知来源；HyperOS 可能需关闭安全扫描 |
