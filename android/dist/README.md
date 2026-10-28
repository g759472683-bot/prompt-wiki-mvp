# APK artifacts

APK 不进 Git（65MB 二进制），构建后放在这里，或作为 GitHub/Gitee Release 资产上传：

```text
promptwiki-0.6.0.apk
```

- 构建：先运行 `..\scripts\fetch-vosk-model.ps1`，再 `gradle assembleDebug`。
- 手机下载：当前内网由 `http://192.168.137.1:8080/app-debug.apk` 提供，不依赖 Git。
- 版本说明与安装步骤见 [`../README.md`](../README.md)。
