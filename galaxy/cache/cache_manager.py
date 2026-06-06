"""3-tier cache manager using fakeredis."""
import json
import time
import logging
from pathlib import Path
from typing import Any, Optional
import fakeredis

from galaxy.config import Config

log = logging.getLogger("galaxy.cache")


class CacheManager:
    """3-tier cache: L1 (hot/memory), L2 (warm/redis), L3 (cold/disk)."""
    
    def __init__(self):
        self._l1 = fakeredis.FakeRedis(decode_responses=True)  # hot
        self._l2 = fakeredis.FakeRedis(decode_responses=True)  # warm
        self._l3_dir = Config.CACHE_DIR / "l3"
        self._l3_dir.mkdir(parents=True, exist_ok=True)
    
    async def get(self, key: str) -> Optional[Any]:
        """Check L1 → L2 → L3. Returns value or None."""
        # L1
        val = self._l1.get(key)
        if val:
            log.debug(f"Cache L1 hit: {key}")
            return json.loads(val)
        # L2
        val = self._l2.get(key)
        if val:
            log.debug(f"Cache L2 hit: {key}")
            self._l1.setex(key, Config.CACHE_L1_TTL, val)
            return json.loads(val)
        # L3
        l3_path = self._l3_dir / f"{key}.json"
        if l3_path.exists():
            data = json.loads(l3_path.read_text())
            if time.time() - data.get("_ts", 0) < Config.CACHE_L3_TTL:
                log.debug(f"Cache L3 hit: {key}")
                val_str = json.dumps(data["value"])
                self._l2.setex(key, Config.CACHE_L2_TTL, val_str)
                self._l1.setex(key, Config.CACHE_L1_TTL, val_str)
                return data["value"]
        return None
    
    async def set(self, key: str, value: Any, tier: str = "L1") -> None:
        """Store value in specified tier (cascades down)."""
        val_str = json.dumps(value)
        if tier in ("L1", "L2", "L3"):
            self._l1.setex(key, Config.CACHE_L1_TTL, val_str)
        if tier in ("L2", "L3"):
            self._l2.setex(key, Config.CACHE_L2_TTL, val_str)
        if tier == "L3":
            l3_path = self._l3_dir / f"{key}.json"
            l3_path.write_text(json.dumps({"value": value, "_ts": time.time()}))
    
    async def invalidate(self, key: str) -> None:
        """Remove from all tiers."""
        self._l1.delete(key)
        self._l2.delete(key)
        l3_path = self._l3_dir / f"{key}.json"
        if l3_path.exists():
            l3_path.unlink()
