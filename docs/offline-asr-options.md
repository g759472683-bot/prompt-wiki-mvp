# 离线中文 ASR 选型（2026-10）

> 目标：Redmi K80 / HyperOS 无 Google 语音服务，App 仍能连续中文转写；先走端侧（B 方案），不依赖云 key。
> 约束：Android、离线、流式、中文、可商用、能塞进 APK。

## 1. GitHub 候选

| 项目 | Stars | License | 最近更新 | Android | 中文模型 | 结论 |
|---|---:|---|---|---|---|---|
| [Vosk](https://github.com/alphacep/vosk-api) | 15.2k | Apache-2.0 | 2026-10-15 | 官方 AAR + JNA | small 42MB / big 1.3GB | **先接这个**：最简单、真流式 |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | 15.5k | Apache-2.0 | 2026-10-25 | AAR + Kotlin API | mobile 51.8MB / zh-int8 126.5MB / xlarge 570MB | **准确率升级首选**：更新快、模型多，但接入更重 |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) | 54.7k | MIT | 2026-10-19 | Android 示例 | tiny/base 75–142MB | 不是真流式；适合整段转写 |
| [FunASR](https://github.com/modelscope/FunASR) | 20.8k | MIT | 2026-10-22 | 无官方 Android SDK | Paraformer | 服务端/ONNX 为主，端侧要自己接 |
| [WeNet](https://github.com/wenet-e2e/wenet) | 5.2k | Apache-2.0 | 2026-09-07 | 有 runtime | 中文流式 | 生产级，但 Android 集成复杂 |

## 2. Vosk 中文模型

来自 [Vosk Models](https://alphacephei.com/vosk/models)：

| 模型 | 大小 | WER（SpeechIO-02 / 06 / THCHS） | 用途 |
|---|---:|---|---|
| `vosk-model-small-cn-0.22` | 42MB | 23.54 / 38.29 / 17.15 | **当前选择**：手机、离线 |
| `vosk-model-cn-0.22` | 1.3GB | 13.98 / 27.30 / 7.43 | 服务端/高精度，不适合 APK |

- 小模型运行时约 300MB 内存；
- 对面试长句的专有名词、数字会有错；现场用关键词/短问句更稳；
- 大模型准确率明显好，但 1.3GB 不适合直接塞 APK。

## 3. 为什么先 Vosk

1. 官方 Android AAR 直接依赖，不用自己编 NDK；
2. `SpeechService` 已封装 `AudioRecord` + 流式识别；
3. 42MB 模型 + 23MB native，APK 约 65MB；
4. 完全离线，不需要腾讯/阿里 key；
5. 后续要换 sherpa，只换 `VoskSpeechController` 这一层。

## 4. 已落地

- `android/app/src/main/assets/model-cn/`：Vosk 小中文模型 + uuid；
- `VoskSpeechController.kt`：`StorageService.unpack` → `Model` → `Recognizer` → `SpeechService`；
- 首次启动把 assets 复制到 external files，之后直接加载；
- 现场页“开始离线语音”连续听，partial 实时更新输入框，停顿后出 final；
- 保留手动输入 + 系统键盘语音兜底；
- 只打包 `arm64-v8a`，APK 65MB。

## 5. 升级路径

如果 Vosk 小模型在真实面试里错得太多：

1. 先换 `vosk-model-cn-0.22`（1.3GB，仅内测 sideload，不进 APK）；
2. 或换 **sherpa-onnx `sherpa-onnx-streaming-zipformer-zh-int8-2025-06-30`**（压缩包 126.5MB，模型更新、准确率更高）；
3. 或只对“问题检测”做关键词/领域词表，不追求全文准确。

## 6. 来源

- [Vosk API](https://github.com/alphacep/vosk-api) · [Vosk Models](https://alphacephei.com/vosk/models) · [Vosk Android Demo](https://github.com/alphacep/vosk-android-demo)
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) · [Android docs](https://k2-fsa.github.io/sherpa/onnx/android/index.html) · [Chinese streaming models](https://k2-fsa.github.io/sherpa/onnx/pretrained_models/online-transducer/zipformer-transducer-models.html)
- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) · [FunASR](https://github.com/modelscope/FunASR) · [WeNet](https://github.com/wenet-e2e/wenet)
