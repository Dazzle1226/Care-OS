from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.config import settings


def simple_tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^\w\u4e00-\u9fa5]+", text.lower()) if token]


def hash_embedding(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    tokens = simple_tokenize(text)
    if not tokens:
        return vec

    for tok in tokens:
        idx = abs(hash(tok)) % dim
        sign = 1.0 if (hash(tok + "_sign") % 2 == 0) else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


class ProviderUnavailableError(RuntimeError):
    pass


@dataclass(slots=True)
class EmbeddingResponse:
    vector: list[float]
    provider: str
    model: str


class BaseEmbeddingProvider:
    provider_name = "base"
    model_name = "unknown"

    def embed(self, text: str) -> EmbeddingResponse:
        raise NotImplementedError


class HashEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "hash"
    model_name = "hash-embedding"

    def embed(self, text: str) -> EmbeddingResponse:
        return EmbeddingResponse(
            vector=hash_embedding(text, dim=settings.embedding_dim),
            provider=self.provider_name,
            model=self.model_name,
        )


class OpenAICompatibleEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "openai_compatible"

    def __init__(self, *, api_key: str | None, base_url: str, model_name: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name

    def embed(self, text: str) -> EmbeddingResponse:
        if not self.api_key:
            raise ProviderUnavailableError("OPENAI_API_KEY not configured")
        payload = {"model": self.model_name, "input": text}
        req = urllib.request.Request(
            url=f"{self.base_url}/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=settings.provider_timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            vector = list(body["data"][0]["embedding"])[: settings.embedding_dim]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ProviderUnavailableError(f"Embedding request failed: {exc}") from exc
        return EmbeddingResponse(vector=vector, provider=self.provider_name, model=self.model_name)


class EmbeddingProviderRouter:
    def __init__(self) -> None:
        self.primary = settings.embedding_provider.lower()
        self.fallback = settings.embedding_fallback_provider.lower()

    def _build_provider(self, name: str) -> BaseEmbeddingProvider:
        if name in {"openai", "openai_compatible", "auto"}:
            return OpenAICompatibleEmbeddingProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model_name=settings.openai_embedding_model,
            )
        if name == "hash":
            return HashEmbeddingProvider()
        raise ProviderUnavailableError(f"Unknown embedding provider: {name}")

    def embed(self, text: str) -> EmbeddingResponse:
        attempts = [self.primary]
        if self.fallback not in attempts:
            attempts.append(self.fallback)
        if "hash" not in attempts:
            attempts.append("hash")

        last_error: Exception | None = None
        for name in attempts:
            provider_name = "openai_compatible" if name == "auto" else name
            provider = self._build_provider(provider_name)
            try:
                return provider.embed(text)
            except ProviderUnavailableError as exc:
                last_error = exc
                continue
        raise ProviderUnavailableError(str(last_error or "No embedding provider available"))


@dataclass(slots=True)
class RerankResponse:
    score: float
    provider: str
    model: str


class HeuristicRerankProvider:
    provider_name = "heuristic"
    model_name = "heuristic-rerank-v1"

    def rerank(self, *, dense_score: float, sparse_score: float, profile_score: float, history_score: float, policy_score: float, safety_penalty: float, confidence: float = 1.0) -> RerankResponse:
        total = (
            0.42 * dense_score
            + 0.16 * sparse_score
            + 0.14 * profile_score
            + 0.1 * history_score
            + 0.1 * policy_score
            + 0.08 * confidence
            - 0.16 * safety_penalty
        )
        return RerankResponse(score=round(total, 4), provider=self.provider_name, model=self.model_name)

