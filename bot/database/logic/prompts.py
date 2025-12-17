import uuid
from typing import Optional

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


async def get_all_prompts(pool: Pool, user_id: int) -> list[dict]:
    async with pool.acquire() as conn:
        records = await conn.fetch(
            "SELECT * FROM custom_prompts WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
        return [dict(record) for record in records]


async def get_prompt_by_title(pool: Pool, title: str, user_id: int) -> dict | None:
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM custom_prompts WHERE title = $1 AND user_id = $2",
            title,
            user_id,
        )
        return dict(record) if record else None


async def update_prompt(
    pool: Pool,
    prompt_id: str,
    user_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    is_public: Optional[bool] = None,
) -> bool:
    updates = []
    params = []
    param_counter = 1

    if title is not None:
        updates.append(f"title = ${param_counter}")
        params.append(title)
        param_counter += 1

    if content is not None:
        updates.append(f"content = ${param_counter}")
        params.append(content)
        param_counter += 1

    if is_public is not None:
        updates.append(f"is_public = ${param_counter}")
        params.append(is_public)
        param_counter += 1

    if not updates:
        return False

    params.extend([prompt_id, user_id])

    query = f"""
        UPDATE custom_prompts 
        SET {', '.join(updates)}
        WHERE id = ${param_counter} AND user_id = ${param_counter + 1}
        RETURNING id
    """

    async with pool.acquire() as conn:
        result = await conn.fetchrow(query, *params)
        return bool(result)


async def remove_prompt(pool: Pool, prompt_id: str) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM custom_prompts WHERE id = $1",
            prompt_id,
        )
        return result != "DELETE 0"
