import json
from typing import Optional

from asyncpg import Pool

from bot.database.bootstrap import sync_all as bootstrap_sync_all
from bot.database.constants import DEFAULT_USER_SETTINGS


async def sync_database_schema(pool: Pool):
    await bootstrap_sync_all(pool)


async def get_chat_val(pool: Pool, chat_id: int, name: str):
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT value FROM features WHERE chat_id=$1 AND feature_name=$2",
            chat_id,
            name,
        )
        return json.loads(value) if value is not None else None


async def set_chat_val(pool: Pool, chat_id: int, name: str, value):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO features (chat_id, feature_name, value)
            VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (chat_id, feature_name)
            DO UPDATE SET value = EXCLUDED.value
            """,
            chat_id,
            name,
            json.dumps(value),
        )


async def is_enabled(pool: Pool, chat_id: int, name: str) -> bool:
    val = await get_chat_val(pool, chat_id, name)
    return bool(val)


async def toggle_chat_val(
    pool: Pool, chat_id: int, name: str, enable: Optional[bool] = None
) -> bool:
    current = await get_chat_val(pool, chat_id, name)
    new_val = bool(enable) if enable is not None else not bool(current)
    await set_chat_val(pool, chat_id, name, new_val)
    return new_val


async def ensure_global_user(pool: Pool, user_id: int):
    """Вспомогательная функция для проверки существования глобального юзера"""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO global_users (user_id, language_code) VALUES ($1, 'en')
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )


async def get_user_val(pool: Pool, user_id: int, name: str):
    await ensure_global_user(pool, user_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM global_users WHERE user_id = $1", user_id
        )

        settings_raw = row.get("settings") if row else None

        # Парсинг JSON
        if isinstance(settings_raw, str):
            try:
                settings = json.loads(settings_raw)
            except:
                settings = {}
        elif isinstance(settings_raw, dict):
            settings = settings_raw
        else:
            settings = {}

        if name in settings:
            return settings[name]

        # Возврат дефолтного значения
        for s_name, _, _, default, _ in DEFAULT_USER_SETTINGS:
            if s_name == name:
                return default
        return None


async def set_user_val(pool: Pool, user_id: int, name: str, value):
    await ensure_global_user(pool, user_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings FROM global_users WHERE user_id = $1", user_id
        )
        settings_raw = row.get("settings") if row else {}

        if isinstance(settings_raw, str):
            try:
                settings = json.loads(settings_raw)
            except:
                settings = {}
        elif isinstance(settings_raw, dict):
            settings = settings_raw
        else:
            settings = {}

        settings[name] = value

        await conn.execute(
            "UPDATE global_users SET settings = $1::jsonb WHERE user_id = $2",
            json.dumps(settings, ensure_ascii=False),
            user_id,
        )
