"""Check DeepSeek connectivity and JSON mode. Run with DEEPSEEK_API_KEY set."""

from __future__ import annotations

import json
import os
import time

import httpx

key = os.environ["DEEPSEEK_API_KEY"]
base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

payload = {
    "model": model,
    "messages": [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": 'Return exactly this JSON: {"ok": true}'},
    ],
    "temperature": 0,
    "response_format": {"type": "json_object"},
    "max_tokens": 100,
}

started = time.perf_counter()
response = httpx.post(
    f"{base}/chat/completions",
    headers={"Authorization": f"Bearer {key}"},
    json=payload,
    timeout=90,
)
elapsed = int((time.perf_counter() - started) * 1000)
print("status", response.status_code, "ms", elapsed)
if response.status_code != 200:
    print(response.text[:1000])
    raise SystemExit(1)
data = response.json()
content = data["choices"][0]["message"]["content"]
print("content", content)
print("usage", json.dumps(data.get("usage"), ensure_ascii=False))
