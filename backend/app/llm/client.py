from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx


class LLMError(RuntimeError):
    """Raised when the provider fails after retries or rejects the request."""


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    model: str = ""


class LLMClient(Protocol):
    def chat_json(
        self, system: str, user: str, max_tokens: int | None = None
    ) -> LLMResult: ...


class DeepSeekClient:
    """Minimal OpenAI-compatible chat client for DeepSeek JSON mode."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        timeout: float = 90.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self._client = client or httpx.Client(timeout=timeout)

    def _post(self, payload: dict) -> httpx.Response:
        return self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )

    def chat_json(
        self, system: str, user: str, max_tokens: int | None = None
    ) -> LLMResult:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        last_error = "unknown error"
        for attempt in range(self.max_retries + 1):
            started = time.perf_counter()
            try:
                response = self._post(payload)
            except httpx.HTTPError as exc:
                last_error = f"network error: {exc.__class__.__name__}"
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(last_error) from exc

            if response.status_code == 401:
                raise LLMError("DeepSeek authentication failed (check DEEPSEEK_API_KEY)")
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"DeepSeek HTTP {response.status_code}"
                if attempt < self.max_retries:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise LLMError(last_error)
            if response.status_code != 200:
                raise LLMError(
                    f"DeepSeek HTTP {response.status_code}: {response.text[:300]}"
                )

            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                raise LLMError("DeepSeek returned no choices")
            content = (choices[0].get("message") or {}).get("content") or ""
            if not content.strip():
                raise LLMError("DeepSeek returned empty content")

            usage = data.get("usage") or {}
            return LLMResult(
                content=content,
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                latency_ms=int((time.perf_counter() - started) * 1000),
                model=str(data.get("model") or self.model),
            )

        raise LLMError(last_error)
