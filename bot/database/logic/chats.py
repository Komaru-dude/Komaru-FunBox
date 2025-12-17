from asyncpg import Pool


async def add_chat(pool: Pool, chat_id: int, chat_type: str = "private"):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO chats (chat_id, type) VALUES ($1, $2)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            chat_id,
            chat_type,
        )


async def get_chat(pool: Pool, chat_id: int) -> dict | None:
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM chats WHERE chat_id = $1",
            chat_id,
        )
        return dict(record) if record else None


async def chat_exists(pool: Pool, chat_id: int) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1)",
            chat_id,
        )


async def get_all_chats(pool: Pool) -> list[int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id FROM chats")
        return [row["chat_id"] for row in rows]
