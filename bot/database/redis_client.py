import asyncio
from typing import Optional

from redis.asyncio import Redis


class RedisManager:
    def __init__(self):
        self._redis: Optional[Redis] = None

    async def connect(self, host: str = "redis", port: int = 6379, db: int = 0):
        self._redis = Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        for attempt in range(5):
            try:
                await self._redis.ping()  # type: ignore
                return
            except Exception:
                if attempt == 4:
                    raise
                await asyncio.sleep(1)

    async def close(self):
        if self._redis:
            await self._redis.close()

    @property
    def client(self) -> Redis:
        if self._redis is None:
            raise RuntimeError(
                "RedisManager не инициализирован. Сначала вызовите connect."
            )
        return self._redis


redis_db = RedisManager()
