import time

from asyncpg import Pool

from bot.database.logic.users import add_global_user


async def get_user_tier(pool: Pool, user_id: int) -> int:
    async with pool.acquire() as conn:
        expire = await conn.fetchval(
            "SELECT premium_expire FROM global_users WHERE user_id = $1",
            user_id,
        )
        if expire is None:
            await add_global_user(pool, user_id)
            return 0

        now = int(time.time())
        if expire and expire > now:
            return 1

        if expire and expire > 0 and expire <= now:
            await conn.execute(
                "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
                0,
                user_id,
            )

        return 0


async def set_user_tier(pool: Pool, user_id: int, tier: int):
    async with pool.acquire() as conn:
        if tier and tier > 0:
            now = int(time.time())
            expire = now + (10 * 365 * 24 * 60 * 60)
            await conn.execute(
                "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
                expire,
                user_id,
            )
        else:
            await conn.execute(
                "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
                0,
                user_id,
            )


async def get_premium_expire(pool: Pool, user_id: int) -> int:
    async with pool.acquire() as connection:
        result = await connection.fetchval(
            "SELECT premium_expire FROM global_users WHERE user_id = $1", user_id
        )
        return result or 0


async def set_premium_expire(pool: Pool, user_id: int, expire_ts: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
            expire_ts,
            user_id,
        )


async def add_premium_days(pool: Pool, user_id: int, days: int) -> int:
    async with pool.acquire() as conn:
        expire = await conn.fetchval(
            "SELECT premium_expire FROM global_users WHERE user_id = $1",
            user_id,
        )
        if expire is None:
            await add_global_user(pool, user_id)
            expire = 0

        now = int(time.time())
        add_seconds = int(days) * 24 * 60 * 60

        if not expire or expire <= now:
            new_expire = now + add_seconds
        else:
            new_expire = expire + add_seconds

        await conn.execute(
            "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
            new_expire,
            user_id,
        )
        return new_expire


async def remove_premium_days(pool: Pool, user_id: int, days: int) -> int:
    """
    Remove days from premium_expire timestamp.
    Returns remaining expiry timestamp, or 0 if premium expires.
    """
    async with pool.acquire() as conn:
        expire = await conn.fetchval(
            "SELECT premium_expire FROM global_users WHERE user_id = $1",
            user_id,
        )
        if expire is None:
            await add_global_user(pool, user_id)
            return 0

        now = int(time.time())
        if not expire or expire <= now:
            return 0

        sub_seconds = int(days) * 24 * 60 * 60
        new_expire = expire - sub_seconds

        if new_expire <= now:
            await conn.execute(
                "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
                0,
                user_id,
            )
            return 0

        await conn.execute(
            "UPDATE global_users SET premium_expire = $1 WHERE user_id = $2",
            new_expire,
            user_id,
        )
        return new_expire


async def is_premium_user(pool: Pool, user_id: int) -> bool:
    async with pool.acquire() as connection:
        result = await connection.fetchval(
            "SELECT premium_expire FROM global_users WHERE user_id = $1", user_id
        )
        now = int(time.time())
        return bool(result and result > now)
