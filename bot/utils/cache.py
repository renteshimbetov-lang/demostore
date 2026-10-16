import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from bot.config import config

logger = logging.getLogger("CacheManager")


class CacheManager:
    """
    Ikki bosqichli kesh tizimi:
    - L1 (RAM): Server xotirasidagi ultra-tezkor kesh (0ms kechikish).
    - L2 (Redis): Agar REDIS_URL berilgan bo'lsa, server qayta yuklanganda ham
                  rasmlar va ma'lumotlar saqlanib qoladi.
    - Zero-failure fallback: Agar Redis ulanmagan yoki vaqtincha uzilgan bo'lsa,
      tizim hech qanday xatoliksiz L1 xotira keshida ishlashni davom ettiradi.
    """

    def __init__(self, redis_url: Optional[str] = None, redis_client=None):
        self.redis_url = (redis_url if redis_url is not None else config.redis_url).strip()
        self._redis_client = redis_client
        self._redis_enabled = redis_client is not None
        self._init_attempted = redis_client is not None
        # L1 Memory Cache: key -> (bytes, content_type, expires_at)
        self._memory_cache: Dict[str, Tuple[bytes, str, float]] = {}
        # L1 JSON Cache: key -> (json_str, expires_at)
        self._json_cache: Dict[str, Tuple[str, float]] = {}
        self._lock = asyncio.Lock()

    async def _ensure_redis(self):
        """Redis ulanishini xavfsiz va bir marta ishga tushirish (Lazy Init)"""
        if self._init_attempted:
            return
        async with self._lock:
            if self._init_attempted:
                return
            self._init_attempted = True

            if not self.redis_url:
                logger.info("REDIS_URL ko'rsatilmagan. Standart L1 xotira keshi ishlatiladi.")
                return

            try:
                import redis.asyncio as aioredis
                self._redis_client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=False,
                    socket_timeout=3.0,
                    socket_connect_timeout=3.0
                )
                await self._redis_client.ping()
                self._redis_enabled = True
                logger.info("Redis kesh serveriga muvaffaqiyatli ulandi!")
            except Exception as e:
                logger.warning(f"Redis keshga ulanib bo'lmadi ({e}). L1 xotira keshiga o'tildi.")
                self._redis_enabled = False
                self._redis_client = None

    def is_redis_active(self) -> bool:
        """Redis hozirda faol ishlayotganligini bildiradi"""
        return self._redis_enabled and self._redis_client is not None

    def _cleanup_memory_if_needed(self):
        """RAM kesh hajmi 500 tadan oshganda eskirganlarini tozalash"""
        now = time.time()
        if len(self._memory_cache) > 500:
            expired = [k for k, v in self._memory_cache.items() if v[2] <= now]
            for k in expired:
                self._memory_cache.pop(k, None)
            if len(self._memory_cache) > 500:
                oldest = sorted(self._memory_cache.keys(), key=lambda k: self._memory_cache[k][2])
                for k in oldest[:100]:
                    self._memory_cache.pop(k, None)

    async def get_photo(self, file_id: str) -> Optional[Tuple[bytes, str]]:
        """
        Telegram file_id bo'yicha rasmni keshdan olish.
        1. L1 RAM tekshiriladi (0ms)
        2. L2 Redis tekshiriladi (Redis bo'lsa)
        """
        now = time.time()

        # 1. L1 RAM kesh
        cached_mem = self._memory_cache.get(file_id)
        if cached_mem:
            data, ctype, expires_at = cached_mem
            if now < expires_at:
                return data, ctype

        # 2. L2 Redis kesh
        await self._ensure_redis()
        if self.is_redis_active():
            try:
                key = f"demostore:photo:{file_id}".encode("utf-8")
                val = await self._redis_client.get(key)
                if val:
                    sep = val.find(b"\n")
                    if sep != -1:
                        ctype = val[:sep].decode("utf-8")
                        data = val[sep + 1:]
                        # L1 xotiraga ham 12 soatga yozib qo'yamiz
                        self._memory_cache[file_id] = (data, ctype, now + 43200)
                        return data, ctype
            except Exception as e:
                logger.debug(f"Redisdan rasm olishda ogohlantirish: {e}")

        return None

    async def set_photo(
        self,
        file_id: str,
        data: bytes,
        content_type: str,
        ttl_seconds: int = 604800  # Sukut bo'yicha 7 kun
    ):
        """
        Rasmni L1 RAM va L2 Redis keshiga saqlash.
        """
        now = time.time()
        self._cleanup_memory_if_needed()
        # L1 RAM keshda kamida 12 soat saqlanadi
        self._memory_cache[file_id] = (data, content_type, now + min(ttl_seconds, 43200))

        await self._ensure_redis()
        if self.is_redis_active():
            try:
                key = f"demostore:photo:{file_id}".encode("utf-8")
                payload = content_type.encode("utf-8") + b"\n" + data
                await self._redis_client.set(key, payload, ex=ttl_seconds)
            except Exception as e:
                logger.debug(f"Redisga rasm yozishda ogohlantirish: {e}")

    async def get_json(self, key: str) -> Optional[Any]:
        """Keshdan ixtiyoriy JSON ma'lumotni o'qish"""
        now = time.time()
        cached = self._json_cache.get(key)
        if cached:
            raw_str, expires_at = cached
            if now < expires_at:
                try:
                    return json.loads(raw_str)
                except Exception:
                    pass

        await self._ensure_redis()
        if self.is_redis_active():
            try:
                redis_key = f"demostore:data:{key}".encode("utf-8")
                raw = await self._redis_client.get(redis_key)
                if raw:
                    decoded = raw.decode("utf-8")
                    self._json_cache[key] = (decoded, now + 300)
                    return json.loads(decoded)
            except Exception as e:
                logger.debug(f"Redisdan JSON olishda ogohlantirish: {e}")

        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 3600):
        """Keshga ixtiyoriy JSON ma'lumotni yozish"""
        now = time.time()
        try:
            raw_str = json.dumps(value)
            self._json_cache[key] = (raw_str, now + ttl_seconds)

            await self._ensure_redis()
            if self.is_redis_active():
                redis_key = f"demostore:data:{key}".encode("utf-8")
                await self._redis_client.set(redis_key, raw_str.encode("utf-8"), ex=ttl_seconds)
        except Exception as e:
            logger.debug(f"JSON keshga yozishda ogohlantirish: {e}")

    async def delete(self, key: str):
        """Keshdan kalitni o'chirish"""
        self._memory_cache.pop(key, None)
        self._json_cache.pop(key, None)
        await self._ensure_redis()
        if self.is_redis_active():
            try:
                await self._redis_client.delete(f"demostore:photo:{key}".encode("utf-8"))
                await self._redis_client.delete(f"demostore:data:{key}".encode("utf-8"))
            except Exception:
                pass

    async def close(self):
        """Redis ulanishini xavfsiz yopish"""
        if self._redis_client:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None
            self._redis_enabled = False


# Global kesh menejeri nusxasi
cache_manager = CacheManager()
