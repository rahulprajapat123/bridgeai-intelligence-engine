from __future__ import annotations

import hashlib
import math

from openai import OpenAI

from research_intel.config import Settings
from research_intel.utils import tokenize


class EmbeddingService:
    def __init__(self, settings: Settings, dimension: int = 384) -> None:
        self.settings = settings
        self.dimension = dimension
        self._client: OpenAI | None = None
        if settings.openai_api_key and settings.default_embedding_provider.lower() == "openai":
            self._client = OpenAI(api_key=settings.openai_api_key)
            self.dimension = 1536

    def embed(self, text: str) -> list[float]:
        if self._client:
            try:
                result = self._client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text[:8000],
                )
                return list(result.data[0].embedding)
            except Exception:
                pass
        return self._hash_embedding(text)

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in tokenize(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[index] += sign * (1.0 + min(len(token), 12) / 12.0)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    size = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(size))
    left_norm = math.sqrt(sum(value * value for value in left[:size])) or 1.0
    right_norm = math.sqrt(sum(value * value for value in right[:size])) or 1.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))

