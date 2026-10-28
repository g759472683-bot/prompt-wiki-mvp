# Download the Vosk Chinese small model into Android assets.
# The model is intentionally not committed: 42MB binary, easy to fetch.
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\fetch-vosk-model.ps1

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$asset = Join-Path $root "app\src\main\assets\model-cn"
$zip = Join-Path $env:TEMP "vosk-model-small-cn-0.22.zip"
$extract = Join-Path $env:TEMP "vosk-model-small-cn-0.22-extract"
$url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"

if (Test-Path (Join-Path $asset "uuid")) {
    Write-Host "Vosk model already exists: $asset"
    exit 0
}

New-Item -ItemType Directory -Force -Path $asset | Out-Null
Write-Host "Downloading $url ..."
if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
    & curl.exe -L --retry 3 --retry-delay 2 -o $zip $url
} else {
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
}

if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $extract -Force
Copy-Item (Join-Path $extract "vosk-model-small-cn-0.22\*") $asset -Recurse -Force
Set-Content -Path (Join-Path $asset "uuid") -Value "vosk-small-cn-0.22-v1" -Encoding ASCII

Remove-Item $zip -Force -ErrorAction SilentlyContinue
Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Vosk model ready: $asset"
