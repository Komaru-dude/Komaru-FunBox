import time
from datetime import date, timedelta

from asyncpg import Pool

from bot.database.bootstrap import create_tables as bootstrap_create_tables


async def init_tables(pool: Pool):
    await bootstrap_create_tables(pool)


async def check_cooldown(pool: Pool, user_id: int, command: str, cooldown: int) -> bool:
    now = int(time.time())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT available_at FROM command_cooldowns WHERE user_id = $1 AND command = $2",
            user_id,
            command,
        )

        if row and row["available_at"] > now:
            return False  # Кулдаун активен

        new_time = now + cooldown
        if row:
            await conn.execute(
                "UPDATE command_cooldowns SET available_at = $1 WHERE user_id = $2 AND command = $3",
                new_time,
                user_id,
                command,
            )
        else:
            await conn.execute(
                "INSERT INTO command_cooldowns (user_id, command, available_at) VALUES ($1, $2, $3)",
                user_id,
                command,
                new_time,
            )
        return True


async def register_command_usage(pool: Pool, user_id: int, command_name: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO stats (user_id, command) VALUES ($1, $2)",
            user_id,
            command_name,
        )


async def get_usage_counts(pool: Pool) -> tuple[int, int]:
    async with pool.acquire() as conn:
        day_count = (
            await conn.fetchval(
                "SELECT COUNT(*) FROM stats WHERE created_at >= CURRENT_DATE"
            )
            or 0
        )

        week_count = (
            await conn.fetchval(
                "SELECT COUNT(*) FROM stats WHERE created_at >= NOW() - INTERVAL '7 days'"
            )
            or 0
        )

        return day_count, week_count


async def get_cooldown_remaining(pool: Pool, user_id: int, command: str) -> int:
    now = int(time.time())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT available_at FROM command_cooldowns WHERE user_id = $1 AND command = $2",
            user_id,
            command,
        )
        if row and row["available_at"] > now:
            return row["available_at"] - now
        return 0


async def reset_cooldown(pool: Pool, user_id: int, command: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM command_cooldowns WHERE user_id = $1 AND command = $2",
            user_id,
            command,
        )
