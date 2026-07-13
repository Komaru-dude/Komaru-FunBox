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


async def record_purchase(
    pool: Pool,
    user_id: int,
    days: int,
    stars: int,
    payload=None,
    telegram_charge_id=None,
    provider_charge_id=None,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO premium_purchases
                (user_id, days, stars, payload, telegram_charge_id, provider_charge_id)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            days,
            stars,
            payload,
            telegram_charge_id,
            provider_charge_id,
        )


async def get_premium_stats(pool: Pool) -> dict:
    now = int(time.time())
    async with pool.acquire() as conn:
        active_premiums = await conn.fetchval(
            "SELECT COUNT(*) FROM global_users WHERE premium_expire > $1",
            now,
        )
        totals = await conn.fetchrow("""
            SELECT
                COUNT(*)                 AS purchases,
                COUNT(DISTINCT user_id)  AS buyers,
                COALESCE(SUM(stars), 0)  AS stars,
                COALESCE(SUM(days), 0)   AS days
            FROM premium_purchases
            """)
        window = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '7 days'  THEN stars ELSE 0 END), 0) AS stars_7d,
                COALESCE(SUM(CASE WHEN created_at >= NOW() - INTERVAL '30 days' THEN stars ELSE 0 END), 0) AS stars_30d,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')  AS purchases_7d,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS purchases_30d
            FROM premium_purchases
            """)
        last = await conn.fetchrow(
            "SELECT user_id, days, stars, created_at FROM premium_purchases "
            "ORDER BY created_at DESC LIMIT 1"
        )

    return {
        "active_premiums": active_premiums or 0,
        "total_purchases": totals["purchases"] or 0,
        "unique_buyers": totals["buyers"] or 0,
        "total_stars": totals["stars"] or 0,
        "total_days_sold": totals["days"] or 0,
        "stars_7d": window["stars_7d"] or 0,
        "stars_30d": window["stars_30d"] or 0,
        "purchases_7d": window["purchases_7d"] or 0,
        "purchases_30d": window["purchases_30d"] or 0,
        "last_purchase": dict(last) if last else None,
    }


async def get_top_premium_buyers(pool: Pool, limit: int = 5) -> list:
    """Топ покупателей премиума по потраченным звёздам."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id,
                   COUNT(*)   AS purchases,
                   SUM(stars) AS stars,
                   SUM(days)  AS days
            FROM premium_purchases
            GROUP BY user_id
            ORDER BY stars DESC, purchases DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
