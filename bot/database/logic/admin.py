from asyncpg import Pool


async def ban_media(pool: Pool, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO banned_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            user_id,
        )


async def check_media_ban(pool: Pool, user_id: int) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM banned_users WHERE user_id = $1)", user_id
        )


async def unban_media(pool: Pool, user_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM banned_users WHERE user_id = $1",
            user_id,
        )
