"""Caching must be optional: with no REDIS_URL the app still works (recompute)."""
import bizlens.cache as cache
from bizlens.config import get_settings


def _reset_caches():
    get_settings.cache_clear()
    cache.get_client.cache_clear()


def test_caching_disabled_without_redis_url(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    _reset_caches()
    try:
        assert cache.get_client() is None
        assert cache.get_json("some-key") is None
        cache.set_json("some-key", {"a": 1})  # must be a silent no-op, not raise

        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return [1, 2, 3]

        # With no cache, cached_query computes via loader every time.
        assert cache.cached_query("SELECT 1", loader) == [1, 2, 3]
        assert cache.cached_query("SELECT 1", loader) == [1, 2, 3]
        assert calls["n"] == 2
    finally:
        _reset_caches()
