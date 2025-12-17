from asyncpg import Pool


async def add_active_user(pool: Pool, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO active_users (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )


async def delete_active_user(pool: Pool, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM active_users WHERE user_id = $1",
            user_id,
        )


async def is_active_user(pool: Pool, user_id: int) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM active_users WHERE user_id = $1)",
            user_id,
        )


async def get_active_users_count(pool: Pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM active_users")
