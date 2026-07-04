"""Redis-backed caching for pre-aggregated KPIs and ad-hoc query results.

The dashboard reads KPI cards from Redis (refreshed on a schedule), so page
load is a ~1ms Redis read rather than a live Postgres aggregation. Ad-hoc query
results are cached keyed by a hash of the SQL, so a repeated query is free.

Caching is optional: if REDIS_URL is empty or Redis is unreachable, every cache
op degrades to a no-op (a miss), so the app still works - it just recomputes
from Postgres each time. This lets small/free deployments skip Redis entirely.
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from typing import Any

import redis

from bizlens.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_client() -> redis.Redis | None:
    """Return a Redis client, or None if caching is disabled (no REDIS_URL)."""
    url = get_settings().redis_url
    if not url:
        return None
    return redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)


def sql_key(sql: str) -> str:
    """Deterministic cache key for a SQL string."""
    return "adhoc:" + hashlib.sha256(sql.strip().encode()).hexdigest()[:32]


def get_json(key: str) -> Any | None:
    """Read a cached value, or None on a miss / when caching is unavailable."""
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
    except redis.RedisError as exc:
        logger.warning("cache read failed (%s); treating as a miss", exc)
        return None
    return json.loads(raw) if raw else None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    """Store a value in the cache; silently skip if caching is unavailable."""
    client = get_client()
    if client is None:
        return
    ttl = ttl if ttl is not None else get_settings().kpi_cache_ttl_seconds
    try:
        client.set(key, json.dumps(value, default=str), ex=ttl)
    except redis.RedisError as exc:
        logger.warning("cache write failed (%s); skipping", exc)


def cached_query(sql: str, loader, ttl: int | None = None) -> Any:
    """Return cached result for ``sql`` or compute via ``loader()`` and store."""
    key = sql_key(sql)
    hit = get_json(key)
    if hit is not None:
        return hit
    value = loader()
    set_json(key, value, ttl=ttl)
    return value
