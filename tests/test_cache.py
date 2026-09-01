import asyncio
import pytest
from app.core.cache import TTLCache


@pytest.mark.asyncio
async def test_ttl_cache_basic_ops():
    cache = TTLCache(default_ttl=1)
    
    # Cache miss
    val = await cache.get("test_key")
    assert val is None
    
    # Cache set & hit
    await cache.set("test_key", {"data": 123}, ttl=2)
    hit = await cache.get("test_key")
    assert hit == {"data": 123}
    
    # Invalidate prefix
    await cache.set("signals:1", "sig1")
    await cache.set("signals:2", "sig2")
    await cache.set("other:1", "other1")
    
    removed = await cache.invalidate_prefix("signals:")
    assert removed == 2
    assert await cache.get("signals:1") is None
    assert await cache.get("other:1") == "other1"
    
    # TTL Expiration
    await cache.set("short_lived", "value", ttl=1)
    assert await cache.get("short_lived") == "value"
    await asyncio.sleep(1.1)
    assert await cache.get("short_lived") is None
