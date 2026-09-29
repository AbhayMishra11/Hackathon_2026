import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("coldstorage.cache")

class RedisCacheService:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.is_connected: bool = False
        # In-memory fallback dictionary if Redis is offline
        self._memory_cache: Dict[str, Any] = {}
        self._memory_locks: Dict[str, datetime] = {}

    async def init_redis(self):
        """Initialize connection to Redis instance."""
        if not settings.ENABLE_REDIS:
            logger.info("ℹ️ Redis is disabled via configuration. Using in-memory fallback cache.")
            return

        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2.0
            )
            # Test ping
            await self.redis.ping()
            self.is_connected = True
            logger.info(f" Connected to Redis Cache at {settings.REDIS_URL}")
        except Exception as e:
            self.is_connected = False
            logger.warning(
                f"⚠️ Redis server not reachable at {settings.REDIS_URL} ({e}). "
                f"Falling back gracefully to local memory cache for live metrics and debouncing."
            )

    async def close(self):
        """Close connection to Redis."""
        if self.redis:
            await self.redis.close()
            self.is_connected = False

    async def set_live_zone_metrics(self, zone_id: str, data: Dict[str, Any], ttl: int = None):
        """
        Store latest live metrics for a zone in Redis (Sub-millisecond access for dashboard).
        """
        ttl = ttl or settings.REDIS_METRICS_TTL_SECONDS
        key = f"zone:{zone_id}:live_metrics"
        payload = json.dumps(data)

        if self.is_connected and self.redis:
            try:
                await self.redis.set(key, payload, ex=ttl)
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                self.is_connected = False

        # Memory Fallback
        self._memory_cache[key] = {
            "data": data,
            "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=ttl)
        }

    async def get_live_zone_metrics(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch latest live metrics for a zone from Redis cache.
        """
        key = f"zone:{zone_id}:live_metrics"

        if self.is_connected and self.redis:
            try:
                cached = await self.redis.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                self.is_connected = False

        # Memory Fallback
        cached = self._memory_cache.get(key)
        if cached:
            if datetime.now(timezone.utc).replace(tzinfo=None) < cached["expires_at"]:
                return cached["data"]
            else:
                del self._memory_cache[key]

        return None

    async def acquire_alert_lock(self, zone_id: str, alert_type: str, ttl_seconds: int = 300) -> bool:
        """
        Distributed Debouncing Lock using Redis 'SET key value EX ttl NX'.
        Returns True if lock was acquired (meaning alert SHOULD be dispatched).
        Returns False if lock already exists (debounce active, suppress duplicate SMS).
        """
        lock_key = f"lock:alert:{zone_id}:{alert_type}"

        if self.is_connected and self.redis:
            try:
                # SET with NX=True sets key only if it doesn't already exist
                acquired = await self.redis.set(lock_key, "1", ex=ttl_seconds, nx=True)
                return bool(acquired)
            except Exception as e:
                logger.error(f"Redis alert lock error: {e}")
                self.is_connected = False

        # Memory Fallback
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if lock_key in self._memory_locks:
            if now < self._memory_locks[lock_key]:
                return False # Still locked
            else:
                del self._memory_locks[lock_key]

        self._memory_locks[lock_key] = now + timedelta(seconds=ttl_seconds)
        return True

    async def publish_telemetry_event(self, channel: str, message: Dict[str, Any]):
        """
        Publish telemetry update to Redis Pub/Sub for multi-server WebSocket broadcasting.
        """
        if self.is_connected and self.redis:
            try:
                await self.redis.publish(channel, json.dumps(message))
            except Exception as e:
                logger.error(f"Redis publish error: {e}")

cache_service = RedisCacheService()

