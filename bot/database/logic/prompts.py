import uuid

from asyncpg import Pool


async def create(
    pool: Pool, user_id: int, title: str, content: str, is_public: bool = False
) -> str:
    prompt_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO custom_prompts (id, user_id, title, content, is_public)
            VALUES ($1, $2, $3, $4, $5)
            """,
            prompt_id,
            user_id,
            title,
            content,
            is_public,
        )
    return prompt_id


async def get_by_id(pool: Pool, prompt_id: str) -> dict | None:
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM custom_prompts WHERE id = $1", prompt_id
        )
        return dict(record) if record else None
