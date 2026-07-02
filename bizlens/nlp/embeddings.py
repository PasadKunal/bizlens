"""Text embeddings for the NL-to-SQL retrieval layer.

Two backends, one interface:

* **local** (default) — a deterministic hashing embedder over normalised word
  tokens. No external calls, no model download, so it runs in CI and offline.
  Synonym normalisation ("people"->"users", "signup"->"register", ...) lets it
  bridge phrasing differences beyond raw token overlap.
* **openai** — ``text-embedding-3-small`` when ``EMBED_BACKEND=openai`` and a
  key is set, for true semantic matching.

The embedding dimension is fixed per backend so the pgvector column type stays
consistent. Vectors are L2-normalised, so cosine distance ranks by direction.
"""
from __future__ import annotations

import hashlib
import math
import re

from bizlens.config import get_settings

LOCAL_DIM = 256
OPENAI_DIM = 1536

_STOPWORDS = {
    "the", "a", "an", "of", "for", "to", "in", "on", "by", "me", "show", "get",
    "give", "list", "what", "how", "many", "much", "is", "are", "and", "with",
    "over", "per", "each", "last", "this", "that", "from", "all", "our",
}

# Map surface forms to a canonical token so different phrasings collide.
_SYNONYMS = {
    "people": "user", "users": "user", "customer": "user", "customers": "user",
    "signup": "register", "signups": "register", "signed": "register",
    "sign": "register", "registration": "register", "registrations": "register",
    "source": "channel", "sources": "channel", "channels": "channel",
    "acquisition": "channel", "marketing": "channel",
    "money": "revenue", "sales": "revenue", "earnings": "revenue",
    "income": "revenue", "gmv": "revenue",
    "country": "country", "countries": "country", "region": "country",
    "geography": "country", "geo": "country",
    "active": "active", "dau": "active", "wau": "active", "mau": "active",
    "week": "week", "weekly": "week", "weeks": "week",
    "segment": "segment", "segments": "segment", "tier": "segment",
}


def _tokens(text: str) -> list[str]:
    out = []
    for raw in re.findall(r"[a-z]+", text.lower()):
        if raw in _STOPWORDS:
            continue
        out.append(_SYNONYMS.get(raw, raw))
    return out


def _local_embed(text: str) -> list[float]:
    vec = [0.0] * LOCAL_DIM
    for tok in _tokens(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % LOCAL_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def _openai_embed(text: str) -> list[float]:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def active_backend() -> str:
    settings = get_settings()
    if getattr(settings, "embed_backend", "local") == "openai" and settings.has_openai:
        return "openai"
    return "local"


def embedding_dim() -> int:
    return OPENAI_DIM if active_backend() == "openai" else LOCAL_DIM


def embed(text: str) -> list[float]:
    """Return an L2-normalised embedding for ``text`` using the active backend."""
    if active_backend() == "openai":
        return _openai_embed(text)
    return _local_embed(text)


def to_pgvector(vec: list[float]) -> str:
    """Format a vector as a pgvector literal, e.g. ``[0.1,0.2,...]``."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
