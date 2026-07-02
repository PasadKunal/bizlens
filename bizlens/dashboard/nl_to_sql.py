"""Natural-language to SQL via a lightweight RAG over the query library.

The pre-built queries in :mod:`bizlens.sql.query_library` are embedded (pgvector
in production). A user's natural-language question is embedded and matched to
the closest template by cosine similarity, returning *validated* SQL rather than
free-form generated SQL — safe for a read-only, non-technical self-serve flow.

When pgvector/embeddings are unavailable, a deterministic token-overlap matcher
provides an equivalent (lower-fidelity) fallback so the feature works offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bizlens.sql.query_library import QUERY_LIBRARY


@dataclass
class NLMatch:
    query_name: str
    sql: str
    description: str
    score: float


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
