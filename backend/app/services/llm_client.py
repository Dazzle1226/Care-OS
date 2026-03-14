from __future__ import annotations

import json
from collections.abc import Sequence
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import settings


class LLMUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class LLMClient:
    timeout_seconds: int = 20
    last_provider_name: str = "rule_fallback"
    last_failure_reason: str | None = None
    last_attempts: list[dict[str, str]] | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds == 20:
            self.timeout_seconds = settings.provider_timeout_seconds
        if self.last_attempts is None:
            self.last_attempts = []

    def _post_json_once(self, payload: dict, *, stream: bool = False) -> urllib.response.addinfourl:
        if settings.force_rule_fallback:
            raise LLMUnavailableError("Rule fallback forced by config")
        if not settings.openai_api_key:
            raise LLMUnavailableError("OPENAI_API_KEY not configured")

        if settings.openai_enable_thinking is not None:
            payload["enable_thinking"] = settings.openai_enable_thinking
        if stream:
            payload["stream"] = True
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
            return urllib.request.urlopen(req, timeout=self.timeout_seconds)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise LLMUnavailableError(f"LLM request failed: {exc}") from exc

    def _post_json(self, payload: dict, *, stream: bool = False) -> urllib.response.addinfourl:
        providers = [settings.generation_primary_provider, settings.generation_secondary_provider]
        last_error: Exception | None = None
        self.last_attempts = []
        self.last_failure_reason = None
        for provider in providers:
            if provider == "rule_fallback":
                self.last_attempts.append({"provider": provider, "status": "skipped", "reason": "Generation routed to rule fallback"})
                last_error = LLMUnavailableError("Generation routed to rule fallback")
                continue
            if provider != "openai_compatible":
                self.last_attempts.append({"provider": provider, "status": "failed", "reason": f"Unknown generation provider: {provider}"})
                last_error = LLMUnavailableError(f"Unknown generation provider: {provider}")
                continue
            try:
                response = self._post_json_once(payload, stream=stream)
                self.last_provider_name = provider
                self.last_attempts.append({"provider": provider, "status": "success", "reason": ""})
                self.last_failure_reason = None
                return response
            except LLMUnavailableError as exc:
                self.last_attempts.append({"provider": provider, "status": "failed", "reason": str(exc)})
                last_error = exc
                continue
        self.last_provider_name = "rule_fallback"
        self.last_failure_reason = str(last_error or "No generation provider available")
        details = " | ".join(
            f"{item['provider']}:{item['status']}{'(' + item['reason'] + ')' if item['reason'] else ''}"
            for item in self.last_attempts
        )
        raise LLMUnavailableError(details or self.last_failure_reason)

    @staticmethod
    def _coerce_text_content(content: object) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            text = content.get("text")
            if isinstance(text, str):
                return text
            if isinstance(text, dict):
                value = text.get("value")
                if isinstance(value, str):
                    return value
        if isinstance(content, Sequence):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
                    elif isinstance(text, dict):
                        value = text.get("value")
                        if isinstance(value, str):
                            chunks.append(value)
            return "".join(chunks)
        raise LLMUnavailableError("LLM response parse failed")

    @staticmethod
    def _extract_json_payload(content: str) -> dict:
        text = content.strip()
        if not text:
            raise LLMUnavailableError("LLM response parse failed")

        candidates = [text]
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                candidates.append("\n".join(lines[1:-1]).strip())

        decoder = json.JSONDecoder()
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

            for index, char in enumerate(candidate):
                if char != "{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(candidate[index:])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed

        raise LLMUnavailableError("LLM response parse failed")

    def _read_stream_text(self, resp: urllib.response.addinfourl) -> str:
        parts: list[str] = []
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, dict):
                parts.append(self._coerce_text_content(content))
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text")
                        if isinstance(text, str):
                            parts.append(text)
                        elif isinstance(text, dict):
                            value = text.get("value")
                            if isinstance(value, str):
                                parts.append(value)
        content_text = "".join(parts).strip()
        if not content_text:
            raise LLMUnavailableError("LLM response parse failed")
        return content_text

    def _read_json_response(self, resp: urllib.response.addinfourl, *, stream: bool = False) -> dict:
        try:
            if stream:
                content = self._read_stream_text(resp)
            else:
                body = json.loads(resp.read().decode("utf-8"))
                content = self._coerce_text_content(body["choices"][0]["message"]["content"])
            return self._extract_json_payload(content)
        except Exception as exc:  # pragma: no cover
            raise LLMUnavailableError("LLM response parse failed") from exc

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        payload = {
            "model": settings.openai_chat_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        with self._post_json(payload) as resp:
            return self._read_json_response(resp)

    def generate_multimodal_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_content: list[dict[str, object]],
        stream: bool = False,
    ) -> dict:
        payload = {
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        if stream:
            payload["modalities"] = ["text"]
        with self._post_json(payload, stream=stream) as resp:
            return self._read_json_response(resp, stream=stream)
