"""Natural-language to SQL via a lightweight RAG over the query library.

The pre-built queries in :mod:`bizlens.sql.query_library` are embedded (pgvector
in production). A user's natural-language question is embedded and matched to
the closest template by cosine similarity, returning *validated* SQL rather than
free-form generated SQL - safe for a read-only, non-technical self-serve flow.

When pgvector/embeddings are unavailable, a deterministic token-overlap matcher
provides an equivalent (lower-fidelity) fallback so the feature works offline.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bizlens.sql.query_library import QUERY_LIBRARY

logger = logging.getLogger(__name__)


@dataclass
class NLMatch:
    query_name: str
    sql: str
    description: str
    score: float
    backend: str = "lexical"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def match_query(question: str) -> NLMatch | None:
    """Return the best-matching pre-built query for a natural-language question.

    Uses Jaccard token overlap against each template's description + name as the
    offline fallback. In production this is replaced by pgvector cosine search
    over embeddings of the same corpus.
    """
    q_tokens = _tokens(question)
    if not q_tokens:
        return None

    best: NLMatch | None = None
    for name, meta in QUERY_LIBRARY.items():
        corpus = _tokens(meta["description"] + " " + name.replace("_", " "))
        overlap = q_tokens & corpus
        score = len(overlap) / len(q_tokens | corpus) if corpus else 0.0
        if best is None or score > best.score:
            best = NLMatch(name, meta["sql"].strip(), meta["description"], score)

    return best if best and best.score > 0 else None


def semantic_match(question: str) -> NLMatch | None:
    """Match via pgvector cosine search over the embedded query library.

    Returns ``None`` (so the caller can fall back) if the vector store isn't
    built or the database is unreachable.
    """
    try:
        from bizlens.sql import vector_store

        if not vector_store.is_built():
            return None
        hits = vector_store.search(question, k=1)
    except Exception as exc:  # noqa: BLE001 - any failure -> lexical fallback
        logger.warning("pgvector search unavailable, falling back to lexical: %s", exc)
        return None

    if not hits:
        return None
    h = hits[0]
    from bizlens.nlp.embeddings import active_backend

    return NLMatch(h["name"], h["sql"], h["description"], float(h["similarity"]),
                   backend=active_backend())


def resolve(question: str) -> NLMatch | None:
    """Resolve a question to a query template: pgvector first, lexical fallback."""
    if not question:
        return None
    return semantic_match(question) or match_query(question)
