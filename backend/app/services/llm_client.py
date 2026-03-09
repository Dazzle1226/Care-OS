from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import settings


class LLMUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class LLMClient:
    timeout_seconds: int = 20

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        if settings.force_rule_fallback:
            raise LLMUnavailableError("Rule fallback forced by config")
        if not settings.openai_api_key:
            raise LLMUnavailableError("OPENAI_API_KEY not configured")

        payload = {
            "model": settings.openai_chat_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url=f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise LLMUnavailableError(f"LLM request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:  # pragma: no cover
            raise LLMUnavailableError("LLM response parse failed") from exc
