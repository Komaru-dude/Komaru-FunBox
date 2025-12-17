import time
from datetime import date
from asyncpg import Pool
from bot.database.bootstrap import create_tables as bootstrap_create_tables

async def init_tables(pool: Pool):
    await bootstrap_create_tables(pool)

async def check_cooldown(pool: Pool, user_id: int, command: str, cooldown: int) -> bool:
    now = int(time.time())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT available_at FROM command_cooldowns WHERE user_id = $1 AND command = $2",
            user_id, command
        )
        
        if row and row["available_at"] > now:
            return False # Кулдаун активен

        new_time = now + cooldown
        if row:
            await conn.execute(
                "UPDATE command_cooldowns SET available_at = $1 WHERE user_id = $2 AND command = $3",
                new_time, user_id, command
            )
        else:
             await conn.execute(
                "INSERT INTO command_cooldowns (user_id, command, available_at) VALUES ($1, $2, $3)",
                user_id, command, new_time
            )
        return True

async def register_command_usage(pool: Pool):
    today = date.today()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO uses (day, count) VALUES ($1, 1)
            ON CONFLICT (day) DO UPDATE SET count = uses.count + 1
            """, today
        )
        from datetime import timedelta
        cutoff = today - timedelta(days=7)
        await conn.execute("DELETE FROM uses WHERE day < $1", cutoff)