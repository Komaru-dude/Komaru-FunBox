import json
import asyncpg
from bot.database.models import *
from bot.database.constants import DEFAULT_SETTINGS, DEFAULT_USER_SETTINGS
from bot import logger

async def create_tables(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        async with conn.transaction():
            table_definitions = {
                "users": (USERS_COLUMNS, "PRIMARY KEY (user_id, chat_id)"),
                "features": (FEATURES_COLUMNS, "PRIMARY KEY (chat_id, feature_name)"),
                "banned_users": (BANNED_USERS_COLUMNS, None),
                "chats": (CHATS_COLUMNS, None),
                "global_users": (GLOBAL_USERS_COLUMNS, None),
                "command_cooldowns": (COMMAND_COOLDOWNS_COLUMNS, "PRIMARY KEY (user_id, command)"),
                "uses": (USES_COLUMNS, None),
                "custom_prompts": (CUSTOM_PROMPTS_COLUMNS, None),
                "active_users": (ACTIVE_USERS_COLUMNS, None),
            }

            for table, (columns, pk) in table_definitions.items():
                cols = []
                for name, definition in columns.items():
                    if pk and "PRIMARY KEY" in definition:
                        clean_def = definition.replace("PRIMARY KEY", "").strip().rstrip(",")
                    else:
                        clean_def = definition
                    cols.append(f"{name} {clean_def}")
                if pk:
                    cols.append(pk)

                columns_sql = ",\n".join(cols)
                await conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (\n{columns_sql}\n);")

            # Добавление недостающих колонок (ALTER TABLE)
            for table, (columns, _) in table_definitions.items():
                res = await conn.fetch(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
                )
                existing = {r["column_name"] for r in res}
                for name, definition in columns.items():
                    if name not in existing:
                        clean_def = definition.replace("PRIMARY KEY", "").strip().rstrip(",")
                        try:
                            await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {clean_def}")
                            logger.info(f"Добавлена колонка {name} в таблицу {table}")
                        except asyncpg.exceptions.DuplicateColumnError:
                            pass

async def sync_all(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Синхронизация настроек чатов
            chat_ids_records = await conn.fetch("SELECT DISTINCT chat_id FROM features")
            chat_ids = [r["chat_id"] for r in chat_ids_records]
            setting_names = [s[0] for s in DEFAULT_SETTINGS]

            for chat_id in chat_ids:
                for setting in DEFAULT_SETTINGS:
                    name, _, _, default, _ = setting
                    await conn.execute(
                        """
                        INSERT INTO features (chat_id, feature_name, value)
                        VALUES ($1, $2, $3::jsonb)
                        ON CONFLICT (chat_id, feature_name) DO NOTHING
                        """,
                        chat_id, name, json.dumps(default)
                    )

                await conn.execute(
                    "DELETE FROM features WHERE chat_id = $1 AND feature_name NOT IN (SELECT unnest($2::text[]))",
                    chat_id, setting_names
                )

            # Синхронизация глобальных настроек пользователей
            user_rows = await conn.fetch("SELECT user_id, settings FROM global_users")
            user_setting_names = [s[0] for s in DEFAULT_USER_SETTINGS]

            for row in user_rows:
                user_id = row["user_id"]
                settings_raw = row.get("settings")
                
                # Логика обработки JSON
                if isinstance(settings_raw, dict):
                    u_settings = settings_raw
                elif isinstance(settings_raw, str):
                    try: u_settings = json.loads(settings_raw)
                    except: u_settings = {}
                else:
                    u_settings = {}

                filtered = {k: v for k, v in u_settings.items() if k in user_setting_names}
                changed = filtered.keys() != u_settings.keys()

                for name, _, _, default, _ in DEFAULT_USER_SETTINGS:
                    if name not in filtered:
                        filtered[name] = default
                        changed = True

                if changed:
                    await conn.execute(
                        "UPDATE global_users SET settings = $1::jsonb WHERE user_id = $2",
                        json.dumps(filtered, ensure_ascii=False), user_id
                    )