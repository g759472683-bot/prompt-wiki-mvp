# Android assets

The Vosk Chinese model is **not committed** (42MB binary).

Before building, run:

```powershell
powershell -ExecutionPolicy Bypass -File ..\scripts\fetch-vosk-model.ps1
# from android/: .\scripts\fetch-vosk-model.ps1
```

It downloads `vosk-model-small-cn-0.22` into `model-cn/` and writes the `uuid`
file required by Vosk's `StorageService`.

Model source: <https://alphacephei.com/vosk/models> · Apache-2.0.
