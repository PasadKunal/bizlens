import math

from bizlens.dashboard.nl_to_sql import resolve
from bizlens.nlp.embeddings import LOCAL_DIM, embed, to_pgvector


def test_local_embedding_is_deterministic_and_normalised():
    a = embed("weekly active users by country")
    b = embed("weekly active users by country")
    assert a == b
    assert len(a) == LOCAL_DIM
    assert math.isclose(math.sqrt(sum(x * x for x in a)), 1.0, abs_tol=1e-6)


def test_synonyms_pull_related_phrasings_together():
    def cos(u, v):
        return sum(x * y for x, y in zip(u, v, strict=True))

    # "money"->revenue, "sources"->channel should raise similarity vs an
    # unrelated sentence.
    q = embed("how much money came from different sources")
    related = embed("revenue by channel")
    unrelated = embed("weekly active users by country")
    assert cos(q, related) > cos(q, unrelated)


def test_pgvector_literal_format():
    lit = to_pgvector([0.1, -0.2, 0.3])
    assert lit.startswith("[") and lit.endswith("]")
    assert lit == "[0.100000,-0.200000,0.300000]"


def test_resolve_returns_correct_template():
    # resolve() prefers pgvector when the store is built and falls back to the
    # lexical matcher otherwise; either way it must find the right template.
    match = resolve("weekly active users by country")
    assert match is not None
    assert match.query_name == "wau_by_country"
    assert match.backend in {"lexical", "local", "openai"}
