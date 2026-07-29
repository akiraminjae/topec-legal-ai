"""Embedding generation, provider-abstracted like the AI chat/analysis providers.

`mock` mode produces a deterministic hash-based pseudo-embedding so vector search
is exercisable end-to-end without any external API key (semantic quality is not
representative — Mock mode is clearly labeled everywhere in the UI).
"""
import hashlib

from app.core.config import get_settings

settings = get_settings()


def _mock_embedding(text: str, dim: int) -> list[float]:
    vector: list[float] = []
    seed = text.encode("utf-8")
    counter = 0
    while len(vector) < dim:
        digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for b in digest:
            if len(vector) >= dim:
                break
            vector.append((b / 255.0) * 2 - 1)
        counter += 1
    return vector


def generate_embedding(text: str) -> list[float]:
    if settings.EMBEDDING_PROVIDER == "mock" or not text.strip():
        return _mock_embedding(text or "empty", settings.EMBEDDING_DIM)

    if settings.EMBEDDING_PROVIDER == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=settings.AI_API_KEY, base_url=settings.AI_BASE_URL or None)
        response = client.embeddings.create(model="text-embedding-3-small", input=text[:8000])
        vector = response.data[0].embedding
        return vector[: settings.EMBEDDING_DIM]

    # Unknown provider configured — fail safe to mock rather than crashing the pipeline.
    return _mock_embedding(text, settings.EMBEDDING_DIM)
