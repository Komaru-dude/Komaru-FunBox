import json
import random
import time
from typing import Optional

from asyncpg import Pool

from bot.database.constants import RANK_TO_LEVEL


async def exists(pool: Pool, user_id: int, chat_id: int) -> bool:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1 AND chat_id = $2)",
            user_id,
            chat_id,
        )


async def create(pool: Pool, user_id: int, chat_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, chat_id) VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            user_id,
            chat_id,
        )


async def get_full_data(pool: Pool, user_id: int, chat_id: int) -> dict:
    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1 AND chat_id = $2", user_id, chat_id
        )
        if not record:
            await create(pool, user_id, chat_id)
            record = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1 AND chat_id = $2",
                user_id,
                chat_id,
            )
            if not record:
                return {}
        return dict(record)


async def get_rank(pool: Pool, user_id: int, chat_id: int) -> str:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT rank FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )


async def set_rank(pool: Pool, user_id: int, chat_id: int, rank: str):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, chat_id, rank) VALUES ($1, $2, $3)
            ON CONFLICT (user_id, chat_id) DO UPDATE SET rank = EXCLUDED.rank
            """,
            user_id,
            chat_id,
            rank,
        )


async def check_permission(
    pool: Pool, owner_id: int, user_id: int, chat_id: int, required_level: int
) -> bool:
    if user_id == owner_id:
        return True
    async with pool.acquire() as conn:
        rank = await conn.fetchval(
            "SELECT rank FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )
    return RANK_TO_LEVEL.get(rank, -1) >= required_level


async def inc_message_count(pool: Pool, user_id: int, chat_id: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET message_count = message_count + 1 WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )


async def modify_reputation(
    pool: Pool, user_id: int, chat_id: int, mode: str, value: Optional[int] = 0
):
    if mode not in ["auto_add", "manual_add", "manual_rem"]:
        raise ValueError("Invalid mode")

    if mode == "auto_add":
        # Используем функцию из settings для получения границ
        from bot.database.logic import settings as st  # Избегаем цикличный импорт

        min_rep = await st.get_chat_val(pool, chat_id, "min_random_rep")
        max_rep = await st.get_chat_val(pool, chat_id, "max_random_rep")

        if min_rep is None:
            min_rep = 1
        if max_rep is None:
            max_rep = 4

        value = random.randint(min_rep, max_rep)

    async with pool.acquire() as conn:
        if mode in ["auto_add", "manual_add"]:
            await conn.execute(
                "UPDATE users SET reputation = reputation + $1 WHERE user_id = $2 AND chat_id = $3",
                value,
                user_id,
                chat_id,
            )
        elif mode == "manual_rem":
            await conn.execute(
                "UPDATE users SET reputation = reputation - $1 WHERE user_id = $2 AND chat_id = $3",
                value,
                user_id,
                chat_id,
            )


async def add_history_record(
    pool: Pool, user_id: int, chat_id: int, punishment_type: str, reason: str
):
    async with pool.acquire() as conn:
        if not await exists(pool, user_id, chat_id):
            await create(pool, user_id, chat_id)

        history_json = await conn.fetchval(
            "SELECT history FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )
        history = json.loads(history_json) if history_json else []

        punishment = {
            "type": punishment_type,
            "reason": reason,
            "timestamp": int(time.time()),
        }
        history.append(punishment)

        column_map = {"warn": "warns", "mute": "mutes", "ban": "bans"}
        count_col = column_map.get(punishment_type, f"{punishment_type}s")

        await conn.execute(
            f"""
            UPDATE users 
            SET history = $1::JSONB, {count_col} = {count_col} + 1 
            WHERE user_id = $2 AND chat_id = $3
            """,
            json.dumps(history),
            user_id,
            chat_id,
        )


async def get_history(pool: Pool, user_id: int, chat_id: int) -> list:
    async with pool.acquire() as conn:
        history_json = await conn.fetchval(
            "SELECT history FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )
        return json.loads(history_json) if history_json else []


async def get_user_param(pool: Pool, user_id: int, chat_id: int, param: str):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            f"SELECT {param} FROM users WHERE user_id = $1 AND chat_id = $2",
            user_id,
            chat_id,
        )


async def set_user_param(pool: Pool, user_id: int, chat_id: int, param: str, value):
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE users SET {param} = $1 WHERE user_id = $2 AND chat_id = $3",
            value,
            user_id,
            chat_id,
        )
