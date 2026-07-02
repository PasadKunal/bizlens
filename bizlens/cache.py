"""Redis-backed caching for pre-aggregated KPIs and ad-hoc query results.

The dashboard reads KPI cards from Redis (refreshed on a schedule), so page
load is a ~1ms Redis read rather than a live Postgres aggregation. Ad-hoc query
results are cached keyed by a hash of the SQL, so a repeated query is free.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any

import redis

from bizlens.config import get_settings


@lru_cache
def get_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def sql_key(sql: str) -> str:
    """Deterministic cache key for a SQL string."""
    return "adhoc:" + hashlib.sha256(sql.strip().encode()).hexdigest()[:32]


def get_json(key: str) -> Any | None:
    raw = get_client().get(key)
    return json.loads(raw) if raw else None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    ttl = ttl if ttl is not None else get_settings().kpi_cache_ttl_seconds
    get_client().set(key, json.dumps(value, default=str), ex=ttl)


def cached_query(sql: str, loader, ttl: int | None = None) -> Any:
    """Return cached result for ``sql`` or compute via ``loader()`` and store."""
    key = sql_key(sql)
    hit = get_json(key)
    if hit is not None:
        return hit
    value = loader()
    set_json(key, value, ttl=ttl)
    return value
