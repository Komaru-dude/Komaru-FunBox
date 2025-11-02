import asyncio
import json
import os
import random
import time
import uuid
from datetime import date, timedelta

import asyncpg
from dotenv import load_dotenv

from bot import logger

load_dotenv()

RANK_TO_LEVEL = {
    "Участник": 0,
    "Модератор": 1,
    "Администратор": 2,
    "Владелец": 3,
    "Персонал": 4,
}

DEFAULT_SETTINGS = [
    (
        "who",
        "Основные",
        bool,
        True,
        'реализует функцию объяснения текстового контента, на который пользователь ответил фразой "это что?". Он использует ИИ для генерации краткого и понятного ответа.',
    ),
    (
        "tagall",
        "Основные",
        bool,
        False,
        "Эта функция позволяет ЛЮБОМУ пользователю упоминать ВСЕХ через /tagall\nКрайне не рекомендуется к включению в больших чатах",
    ),
    (
        "autovideo",
        "Медиа",
        bool,
        False,
        "Автоматически загружает видео с поддерживаемых хостингов",
    ),
    (
        "user_prompts",
        "Медиа",
        bool,
        True,
        "Разрешает пользователям создавать и использовать свои промпты",
    ),
    (
        "warn",
        "Модерация",
        bool,
        False,
        'Включает использование варнов для модераторов, требует права "Блокировка пользователей"',
    ),
    (
        "mute",
        "Модерация",
        bool,
        False,
        'Включает использование мьютов для модераторов, требует права "Блокировка пользователей"',
    ),
    (
        "ban",
        "Модерация",
        bool,
        False,
        'Включает использование банов для модераторов, требует права "Блокировка пользователей"',
    ),
    (
        "senddisabledmsg",
        "Уведомления",
        bool,
        True,
        "Отправляет уведомление о том что функция выключена",
    ),
    (
        "auto_eg_free",
        "Уведомления",
        bool,
        False,
        "Каждый четверг отправляет список бесплатных игр в Epic Games",
    ),
    ("alo", "Разное", bool, False, "???"),
    (
        "economy",
        "Экономика",
        bool,
        True,
        "Включает возможность использования экономических команд",
    ),
    ("sendcooldown", "Основные", bool, True, "Отправляет уведомление о кулдаунах"),
    (
        "auto_delete",
        "Модерация",
        bool,
        False,
        "Автоматически удаляет некоторые сообщения бота",
    ),
    (
        "max_warnings",
        "Модерация",
        int,
        3,
        "Максимально кол-во предупреждений после которого пользователь получить мьют",
    ),
    (
        "max_warnings_mute_time",
        "Модерация",
        int,
        7200,
        "Время мьюта за превышение кол-ва предупреждений (в секундах)",
    ),
    (
        "clean_service_msg",
        "Уведомления",
        bool,
        False,
        "Очищает служебные сообщения (к примеру добавление новых участников)",
    ),
    (
        "send_welcome_msg",
        "Приветствия",
        bool,
        False,
        "Разрешает боту отправлять приветственные сообщения",
    ),
    (
        "welcome_message",
        "Приветствия",
        str,
        "Добро пожаловать!",
        "Приветственное сообщение, работает только при включённом send_welcome_msg, разрешается переход между строками с помощью \\n, указание имени пользователя через first_name, last_name, full_name.\nПример: Привет {full_name}",
    ),
    ("give_random_rep", "Модерация", bool, True, "Включает случайную выдачу репутации"),
    (
        "random_rep",
        "Модерация",
        float,
        0.3,
        "Шанс получения случайной репутации (от 0.1 до 1.0)",
    ),
    ("min_random_rep", "Модерация", int, 1, "Минимальное кол-во случайной репутации"),
    ("max_random_rep", "Модерация", int, 4, "Максимальное кол-во случайной репутации"),
]

DEFAULT_USER_SETTINGS = [
    (
        "rob_notif",
        "Уведомления",
        bool,
        True,
        "Сообщает вам в личных сообщениях, если вас ограбили, указывая имя пользователя, который это сделал.",
    )
]

CATEGORIES = list({cat for _, cat, *rest in DEFAULT_SETTINGS})
USER_CATEGORIES = list({cat for _, cat, *rest in DEFAULT_USER_SETTINGS})

USERS_COLUMNS = {
    "user_id": "BIGINT",
    "chat_id": "BIGINT",
    "warns": "INTEGER DEFAULT 0",
    "bans": "INTEGER DEFAULT 0",
    "mutes": "INTEGER DEFAULT 0",
    "reputation": "INTEGER DEFAULT 0",
    "rank": "TEXT DEFAULT 'Участник'",
    "message_count": "INTEGER DEFAULT 0",
    "history": "JSONB DEFAULT '[]'::JSONB",
    "default_model": "TEXT DEFAULT ''",
    "settings": "JSONB DEFAULT '[]'::JSONB",
}

FEATURES_COLUMNS = {
    "chat_id": "BIGINT",
    "feature_name": "TEXT",
    "value": "JSONB NULL",
}

BANNED_USERS_COLUMNS = {
    "user_id": "BIGINT PRIMARY KEY",
}

CHATS_COLUMNS = {
    "chat_id": "BIGINT PRIMARY KEY",
    "type": "TEXT",
    "registered_at": "TIMESTAMP DEFAULT NOW()",
}

GLOBAL_USERS_COLUMNS = {
    "user_id": "BIGINT PRIMARY KEY",
    "language_code": "TEXT DEFAULT 'ru'",
    "registered_at": "TIMESTAMP DEFAULT NOW()",
    "money": "BIGINT DEFAULT 0",
    "bank": "BIGINT DEFAULT 0",
    "name": "TEXT DEFAULT 'Unknown'",
    "items": "JSONB DEFAULT '[]'::JSONB",
    "settings": "JSONB DEFAULT '{}'::JSONB",
}

COMMAND_COOLDOWNS_COLUMNS = {
    "user_id": "BIGINT NOT NULL",
    "command": "TEXT NOT NULL",
    "available_at": "BIGINT NOT NULL",
}

USES_COLUMNS = {
    "day": "DATE PRIMARY KEY",
    "count": "INTEGER NOT NULL DEFAULT 0",
}

CUSTOM_PROMPTS_COLUMNS = {
    "id": "TEXT NOT NULL PRIMARY KEY",
    "user_id": "BIGINT NOT NULL",
    "title": "TEXT NOT NULL",
    "content": "TEXT NOT NULL",
    "is_public": "BOOLEAN DEFAULT FALSE",
    "created_at": "TIMESTAMP DEFAULT NOW()",
}


class Database:
    def __init__(self):
        self.pool = None
        self.owner_id = int(os.getenv("OWNER_ID", 0))
        self._lock = asyncio.Lock()
        self.is_connected = False

    async def ensure_connection(self):
        if not self.is_connected or self.pool is None or self.pool.is_closing():
            await self.connect()
            if self.pool is None or self.pool.is_closing():
                raise ConnectionError(
                    "Failed to establish database connection after ensure_connection."
                )

    async def connect(self):
        async with self._lock:
            if self.is_connected and self.pool and not self.pool.is_closing():
                logger.info("Уже подключены к БД.")
                return

            try:
                logger.info("Подключаемся к базе данных...")
                if self.pool and not self.pool.is_closing():
                    await self.pool.close()
                    logger.info("Существующий пул был закрыт перед переподключением.")

                self.pool = await asyncpg.create_pool(
                    host=os.getenv("DB_HOST"),
                    port=os.getenv("DB_PORT"),
                    user=os.getenv("DB_USER"),
                    password=os.getenv("DB_PASSWORD"),
                    database=os.getenv("DB_NAME"),
                    min_size=5,
                    max_size=20,
                )
                self.is_connected = True
                logger.info("Пул соединений с БД успешно создан.")

                await self.create_tables()
                await self.sync_all()
                logger.info("Успешное подключение и синхронизация с БД.")

            except Exception as e:
                logger.critical(
                    f"Не удалось подключиться к БД или выполнить начальную настройку: {e}"
                )
                self.is_connected = False
                if self.pool:
                    await self.pool.close()
                self.pool = None
                raise

    async def create_tables(self):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Мапа таблиц
                table_definitions = {
                    "users": (USERS_COLUMNS, "PRIMARY KEY (user_id, chat_id)"),
                    "features": (
                        FEATURES_COLUMNS,
                        "PRIMARY KEY (chat_id, feature_name)",
                    ),
                    "banned_users": (BANNED_USERS_COLUMNS, None),
                    "chats": (CHATS_COLUMNS, None),
                    "global_users": (GLOBAL_USERS_COLUMNS, None),
                    "command_cooldowns": (
                        COMMAND_COOLDOWNS_COLUMNS,
                        "PRIMARY KEY (user_id, command)",
                    ),
                    "uses": (USES_COLUMNS, None),
                    "custom_prompts": (CUSTOM_PROMPTS_COLUMNS, None),
                }

                # Создание таблиц
                for table, (columns, pk) in table_definitions.items():
                    cols = []
                    for name, definition in columns.items():
                        # Убираем PRIMARY KEY только если он указан отдельно
                        if pk and "PRIMARY KEY" in definition:
                            clean_def = definition.replace("PRIMARY KEY", "").strip()
                            clean_def = clean_def.rstrip(",").strip()
                        else:
                            clean_def = definition
                        cols.append(f"{name} {clean_def}")
                    if pk:
                        cols.append(pk)

                    columns_sql = ",\n".join(cols)
                    await conn.execute(
                        f"CREATE TABLE IF NOT EXISTS {table} (\n{columns_sql}\n);"
                    )

                # Добавление недостающих колонок
                for table, (columns, _) in table_definitions.items():
                    res = await conn.fetch(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
                    )
                    existing = {r["column_name"] for r in res}
                    for name, definition in columns.items():
                        if name not in existing:
                            clean_def = definition.replace("PRIMARY KEY", "").strip()
                            clean_def = clean_def.rstrip(",").strip()
                            try:
                                await conn.execute(
                                    f"ALTER TABLE {table} ADD COLUMN {name} {clean_def}"
                                )
                            except asyncpg.exceptions.DuplicateColumnError:
                                pass  # Колонка уже существует (редкий случай)

    async def sync_all(self):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                chat_ids_records = await conn.fetch(
                    "SELECT DISTINCT chat_id FROM features"
                )
                chat_ids = [r["chat_id"] for r in chat_ids_records]

                for chat_id in chat_ids:
                    setting_names = [s[0] for s in DEFAULT_SETTINGS]

                    # Добавляем отсутствующие настройки
                    for setting in DEFAULT_SETTINGS:
                        name = setting[0]
                        default = setting[3]

                        await conn.execute(
                            """
                            INSERT INTO features (chat_id, feature_name, value)
                            VALUES ($1, $2, $3::jsonb)
                            ON CONFLICT (chat_id, feature_name) DO NOTHING
                            """,
                            chat_id,
                            name,
                            json.dumps(default),
                        )

                    # Удаляем устаревшие настройки
                    await conn.execute(
                        """
                        DELETE FROM features
                        WHERE chat_id = $1
                        AND feature_name NOT IN (SELECT unnest($2::text[]))
                        """,
                        chat_id,
                        setting_names,
                    )

                # Синхронизация глобальных пользовательских настроек
                user_rows = await conn.fetch("SELECT user_id, settings FROM global_users")
                user_setting_names = [s[0] for s in DEFAULT_USER_SETTINGS]

                for row in user_rows:
                    user_id = row["user_id"]
                    settings_raw = row.get("settings")

                    if settings_raw is None:
                        settings = {}
                    elif isinstance(settings_raw, str):
                        try:
                            parsed = json.loads(settings_raw)
                            settings = parsed if isinstance(parsed, dict) else {}
                        except Exception:
                            settings = {}
                    elif isinstance(settings_raw, dict):
                        settings = settings_raw
                    elif isinstance(settings_raw, list):
                        settings = {}
                    else:
                        settings = {}

                    # Удаляем ключи, которые больше не присутствуют в DEFAULT_USER_SETTINGS
                    filtered = {k: v for k, v in settings.items() if k in user_setting_names}
                    changed = filtered.keys() != settings.keys()

                    # Добавляем отсутствующие настройки по умолчанию
                    for name, _, _, default, _ in DEFAULT_USER_SETTINGS:
                        if name not in filtered:
                            filtered[name] = default
                            changed = True

                    if changed:
                        await conn.execute(
                            "UPDATE global_users SET settings = $1::jsonb WHERE user_id = $2",
                            json.dumps(filtered, ensure_ascii=False),
                            user_id,
                        )

    async def has_permission(
        self, user_id: int, chat_id: int, required_level: int
    ) -> bool:
        if user_id == self.owner_id:
            return True

        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            rank = await conn.fetchval(
                """
                SELECT rank FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """,
                user_id,
                chat_id,
            )

        return RANK_TO_LEVEL.get(rank, -1) >= required_level

    async def set_rank(self, user_id: int, chat_id: int, rank: str):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, chat_id, rank)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, chat_id) 
                DO UPDATE SET rank = EXCLUDED.rank
            """,
                user_id,
                chat_id,
                rank,
            )

    async def user_exists(self, user_id: int, chat_id: int) -> bool:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM users 
                    WHERE user_id = $1 AND chat_id = $2
                )
            """,
                user_id,
                chat_id,
            )

    async def add_user(self, user_id: int, chat_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, chat_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """,
                user_id,
                chat_id,
            )

    async def get_user_rank(self, user_id: int, chat_id: int) -> str:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT rank FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """,
                user_id,
                chat_id,
            )

    async def update_message_count(self, user_id: int, chat_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE users 
                SET message_count = message_count + 1 
                WHERE user_id = $1 AND chat_id = $2
            """,
                user_id,
                chat_id,
            )

    async def get_user_data(self, user_id: int, chat_id: int) -> dict:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT * FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """,
                user_id,
                chat_id,
            )

            if not record:
                await self.add_user(user_id, chat_id)
                record = await conn.fetchrow(
                    """
                    SELECT * FROM users 
                    WHERE user_id = $1 AND chat_id = $2
                """,
                    user_id,
                    chat_id,
                )
                if not record:
                    return {}

            return dict(record)

    async def get_user_param(self, user_id: int, chat_id: int, param: str):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT * FROM users WHERE user_id = $1 AND chat_id = $2""",
                user_id,
                chat_id,
            )
            if not row:
                await self.add_user(user_id, chat_id)
                row = await conn.fetchrow(
                    """SELECT * FROM users WHERE user_id = $1 AND chat_id = $2""",
                    user_id,
                    chat_id,
                )
                if not row:
                    return {}
            return row.get(param)

    async def set_user_param(self, user_id: int, chat_id: int, param: str, value):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE users 
                SET {param} = $1 
                WHERE user_id = $2 AND chat_id = $3
            """,
                value,
                user_id,
                chat_id,
            )

    async def init_chat_settings(self, chat_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            for name, _, _, default, _ in DEFAULT_SETTINGS:
                await conn.execute(
                    """
                    INSERT INTO features (chat_id, feature_name, value)
                    VALUES ($1, $2, $3::jsonb)
                    ON CONFLICT (chat_id, feature_name) DO NOTHING
                    """,
                    chat_id,
                    name,
                    json.dumps(default),
                )

    async def restore_chat_settings(self, chat_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            for name, _, _, default, _ in DEFAULT_SETTINGS:
                await conn.execute(
                    """
                    INSERT INTO features (chat_id, feature_name, value)
                    VALUES ($1, $2, $3::jsonb)
                    ON CONFLICT (chat_id, feature_name) 
                    DO UPDATE SET value = EXCLUDED.value
                    """,
                    chat_id,
                    name,
                    json.dumps(default),
                )

    async def get_setting(self, chat_id: int, name: str):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            value = await conn.fetchval(
                "SELECT value FROM features WHERE chat_id=$1 AND feature_name=$2",
                chat_id,
                name,
            )
            if value is None:
                return None
            return json.loads(value)

    async def set_setting(self, chat_id: int, name: str, value):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
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

    async def is_setting_exists(self, chat_id: int, name: str) -> bool:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM features WHERE chat_id=$1 AND feature_name=$2)",
                chat_id,
                name,
            )

    async def is_setting_enabled(self, chat_id: int, name: str):
        value = await self.get_setting(chat_id, name)
        return bool(value)

    async def toggle_setting(
        self, chat_id: int, name: str, enable: bool = None
    ) -> bool:
        current = await self.get_setting(chat_id, name)
        new_val = bool(enable) if enable is not None else not bool(current)
        await self.set_setting(chat_id, name, new_val)
        return new_val

    async def get_chats_with_setting(self, setting_name: str) -> list[int]:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT chat_id FROM features
                WHERE feature_name = $1 AND value::bool = TRUE
                """,
                setting_name,
            )
            return [row["chat_id"] for row in rows]

    async def mediaban_user(self, user_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO banned_users (user_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
            """,
                user_id,
            )

    async def mediaunban_user(self, user_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM banned_users 
                WHERE user_id = $1
            """,
                user_id,
            )

    async def is_user_mediabanned(self, user_id: int) -> bool:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM banned_users 
                    WHERE user_id = $1
                )
            """,
                user_id,
            )

    async def update_user_history(
        self, user_id: int, chat_id: int, punishment_type: str, reason: str
    ):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            if not await self.user_exists(user_id, chat_id):
                await self.add_user(user_id, chat_id)

            history_json = await conn.fetchval(
                """
                SELECT history FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """,
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

            await conn.execute(
                f"""
                UPDATE users 
                SET 
                    history = $1::JSONB,
                    {punishment_type}s = {punishment_type}s + 1 
                WHERE user_id = $2 AND chat_id = $3
            """,
                json.dumps(history),
                user_id,
                chat_id,
            )

    async def get_user_history(self, user_id: int, chat_id: int) -> list:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            history_json = await conn.fetchval(
                """
                SELECT history FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """,
                user_id,
                chat_id,
            )
            if history_json:
                return json.loads(history_json)
            return []

    async def update_reputation(
        self, user_id: int, chat_id: int, mode: str, value: int = None
    ):
        await self.ensure_connection()
        if mode not in ["auto_add", "manual_add", "manual_rem"]:
            raise ValueError("Invalid mode")

        if mode == "auto_add":
            min_random_rep = await self.get_setting(chat_id, "min_random_rep")
            max_random_rep = await self.get_setting(chat_id, "max_random_rep")
            value = random.randint(min_random_rep, max_random_rep)

        async with self.pool.acquire() as conn:
            if mode in ["auto_add", "manual_add"]:
                await conn.execute(
                    """
                    UPDATE users 
                    SET reputation = reputation + $1 
                    WHERE user_id = $2 AND chat_id = $3
                """,
                    value,
                    user_id,
                    chat_id,
                )
            elif mode == "manual_rem":
                await conn.execute(
                    """
                    UPDATE users 
                    SET reputation = reputation - $1 
                    WHERE user_id = $2 AND chat_id = $3
                """,
                    value,
                    user_id,
                    chat_id,
                )

    async def add_chat(self, chat_id: int, chat_data: dict):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO chats (chat_id, type)
                VALUES ($1, $2)
                ON CONFLICT (chat_id) DO NOTHING""",
                chat_id,
                chat_data.get("type", "private"),
            )

    async def add_global_user(self, user_id: int, user_data: dict = None):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO global_users 
                (user_id, language_code)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET
                    language_code = EXCLUDED.language_code""",
                user_id,
                user_data.get("language_code", "en") if user_data is not None else "en",
            )

    async def get_chat(self, chat_id: int) -> dict:
        """Возвращает информацию о чате"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM chats WHERE chat_id = $1", chat_id
            )
            return dict(record) if record else None

    async def get_global_user(self, user_id: int) -> dict:
        """Возвращает глобальную информацию о пользователе"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM global_users WHERE user_id = $1", user_id
            )
            return dict(record) if record else None

    async def get_global_user_param(self, user_id: int, param: str):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                await self.add_global_user(user_id)
                row = await conn.fetchrow(
                    "SELECT * FROM global_users WHERE user_id = $1",
                    user_id,
                )
                if not row:
                    logger.error(f"Не удалось создать пользователя {user_id}")
                    return None

            value = row.get(param)

            if param == "items":
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except json.JSONDecodeError:
                        return []
                elif value is None:
                    return []

            return value

    async def set_global_user_param(self, user_id: int, param: str, value):
        """Устанавливает параметр пользователю глобально"""

        if param == "items" and isinstance(value, list):
            value = json.dumps(value, ensure_ascii=False)

        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE global_users 
                SET {param} = $1 
                WHERE user_id = $2
            """,
                value,
                user_id,
            )

    async def delete_global_user(self, user_id: int):
        """
        Удаляет глобального пользователя.
        """
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM global_users WHERE user_id = $1
            """,
                user_id,
            )

    async def cleanup_all_expired_items(self):
        logger.debug("🔄 Начинаю очистку истёкших предметов...")
        await self.ensure_connection()
        now = int(time.time())
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id, items FROM global_users")

            for row in rows:
                user_id = row["user_id"]
                items = row["items"]

                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                    except json.JSONDecodeError:
                        items = []
                elif items is None:
                    items = []

                filtered = [
                    item
                    for item in items
                    if isinstance(item, dict) and item.get("expires", now + 1) > now
                ]

                if filtered != items:
                    await self.set_global_user_param(user_id, "items", filtered)
        logger.info("✅ Истёкшие предметы удалены")

    async def chat_exists(self, chat_id: int) -> bool:
        """Проверяет существование чата в базе"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM chats WHERE chat_id = $1)", chat_id
            )

    async def global_user_exists(self, user_id: int) -> bool:
        """Проверяет существование пользователя в глобальной таблице"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM global_users WHERE user_id = $1)", user_id
            )

    async def get_all_chats(self) -> list:
        """Возвращает список всех чатов"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            records = await conn.fetch("SELECT chat_id FROM chats")
            return [r["chat_id"] for r in records]

    async def is_command_available(
        self,
        user_id: int,
        command: str,
        cooldown: int,
    ) -> bool:
        """
        Проверяет, доступна ли команда. Если доступна устанавливает новый кулдаун.

        :param user_id: ID пользователя
        :param command: Название команды
        :param cooldown: Время кулдауна в секундах
        :return: True, если можно выполнять команду, False — если кулдаун ещё активен
        """
        await self.ensure_connection()
        now = int(time.time())
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT available_at FROM command_cooldowns
                WHERE user_id = $1 AND command = $2
                """,
                user_id,
                command,
            )

            if row and row["available_at"] > now:
                return False  # Кулдаун активен

            new_available_at = now + cooldown

            if row:
                await conn.execute(
                    """
                    UPDATE command_cooldowns
                    SET available_at = $3
                    WHERE user_id = $1 AND command = $2
                    """,
                    user_id,
                    command,
                    new_available_at,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO command_cooldowns (user_id, command, available_at)
                    VALUES ($1, $2, $3)
                    """,
                    user_id,
                    command,
                    new_available_at,
                )

            return True

    async def get_cooldown_remaining(
        self,
        user_id: int,
        command: str,
    ) -> int:
        """
        Возвращает оставшееся время кулдауна в секундах.

        :return: Количество секунд до окончания кулдауна или 0
        """
        await self.ensure_connection()
        now = int(time.time())
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT available_at FROM command_cooldowns
                WHERE user_id = $1 AND command = $2
                """,
                user_id,
                command,
            )
            if row:
                return max(0, row["available_at"] - now)
            return 0

    async def reset_cooldown(
        self,
        user_id: int,
        command: str,
    ) -> None:
        """
        Принудительно удаляет кулдаун команды.
        """
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM command_cooldowns
                WHERE user_id = $1 AND command = $2
                """,
                user_id,
                command,
            )

    async def log_command(self):
        today = date.today()
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO uses (day, count)
                    VALUES ($1, 1)
                    ON CONFLICT (day) DO UPDATE SET count = uses.count + 1
                """,
                    today,
                )

                cutoff = today - timedelta(days=7)
                await conn.execute(
                    """
                    DELETE FROM uses WHERE day < $1
                """,
                    cutoff,
                )

    async def get_use_stats(self):
        today = date.today()
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            day_count = (
                await conn.fetchval(
                    """
                SELECT count FROM uses WHERE day = $1
            """,
                    today,
                )
                or 0
            )

            week_count = (
                await conn.fetchval(
                    """
                SELECT SUM(count) FROM uses
                WHERE day >= $1
            """,
                    today - timedelta(days=6),
                )
                or 0
            )

            return day_count, week_count

    async def get_eco_top(self, limit: int = 10) -> list[dict]:
        """
        Возвращает топ по банковским счетам
        """
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, money, bank,
                    (money + bank) AS total
                FROM global_users
                ORDER BY total DESC
                LIMIT $1
                """,
                limit,
            )
        return [dict(row) for row in rows]

    async def has_valid_item(self, user_id: int, item_id: str) -> bool:
        """
        Проверяет, есть ли у пользователя предмет item_id с uses > 0 или uses == -1 и expires ещё не прошёл.
        """
        await self.ensure_connection()
        now = int(time.time())

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT items FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                return False

            items_raw = row["items"] or "[]"
            try:
                items = json.loads(items_raw)
            except Exception:
                items = []

            for item in items:
                if item.get("id") == item_id:
                    expires = item.get("expires")
                    if expires is not None and expires is not False and expires <= now:
                        continue

                    uses = item.get("uses")
                    if uses is not None and uses != -1 and int(uses) <= 0:
                        continue

                    return True
            return False

    async def add_item_to_user(self, user_id: int, shop_item: dict):
        """
        Добавляет предмет из shop_item пользователю.
        Обрабатывает expires и uses, создаёт новый объект.
        """
        await self.ensure_connection()
        now = int(time.time())

        item = {
            "id": shop_item["id"],
            "name": shop_item.get("name"),
            "desc": shop_item.get("desc"),
        }

        expires_raw = shop_item.get("expires", "False")
        if expires_raw == "False" or expires_raw is False:
            item["expires"] = False
        else:
            try:
                duration = int(expires_raw)
                item["expires"] = now + duration
            except Exception:
                item["expires"] = False

        try:
            item["uses"] = int(shop_item.get("uses", 1))
        except Exception:
            item["uses"] = 1

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT items FROM global_users WHERE user_id = $1", user_id
            )
            items_raw = row["items"] or "[]"
            try:
                items = json.loads(items_raw)
            except Exception:
                items = []

            items.append(item)

            items_json = json.dumps(items)

            await conn.execute(
                "UPDATE global_users SET items = $1 WHERE user_id = $2",
                items_json,
                user_id,
            )

    async def use_item(self, user_id: int, item_id: str) -> bool:
        """
        Уменьшает uses у айтема на 1, если uses не равен -1. Если uses стало 0 — удаляет айтем.
        Возвращает True, если предмет найден и использован, иначе False.
        """
        await self.ensure_connection()
        now = int(time.time())

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT items FROM global_users WHERE user_id = $1", user_id
            )
            if not row:
                return False

            items_raw = row["items"] or "[]"
            try:
                items = json.loads(items_raw)
            except Exception:
                items = []

            changed = False

            for i, item in enumerate(items):
                if item.get("id") == item_id:
                    expires = item.get("expires")
                    if expires is not None and expires is not False and expires <= now:
                        continue

                    uses = item.get("uses", 0)
                    if uses == -1:
                        # Бесконечные использования — не уменьшаем, но считаем использованным
                        changed = False
                        return True
                    elif int(uses) <= 0:
                        continue

                    items[i]["uses"] = int(uses) - 1
                    changed = True

                    if items[i]["uses"] <= 0:
                        items.pop(i)
                    break

            if changed:
                items_json = json.dumps(items)
                await conn.execute(
                    "UPDATE global_users SET items = $1 WHERE user_id = $2",
                    items_json,
                    user_id,
                )
                return True

            return False

    async def get_prompt(self, id: str) -> dict:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM custom_prompts WHERE id = $1", id
            )
            return dict(record) if record else None

    async def get_all_prompts(self, user_id: int) -> list[dict]:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT * FROM custom_prompts WHERE user_id = $1", user_id
            )
            return [dict(record) for record in records]

    async def add_prompt(
        self, user_id: int, title: str, content: str, is_public: bool = False
    ) -> str:
        await self.ensure_connection()
        prompt_id = str(uuid.uuid4())
        async with self.pool.acquire() as conn:
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

    async def get_prompt_by_title(self, title: str, user_id: int) -> str:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM custom_prompts WHERE title = $1 AND user_id = $2
            """,
                title,
                user_id,
            )
            return row if row else None

    async def remove_prompt_by_id(self, prompt_id: str) -> None:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM custom_prompts WHERE id = $1", prompt_id)

    async def init_user_settings(self, user_id: int):
        """
        Инициализирует глобальные настройки пользователя значениями по умолчанию.
        """
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                await self.add_global_user(user_id)
                row = await conn.fetchrow(
                    "SELECT settings FROM global_users WHERE user_id = $1",
                    user_id,
                )

            settings_raw = row.get("settings") if row else None

            # Приводим к словарю
            settings = {}
            if settings_raw is None:
                settings = {}
            elif isinstance(settings_raw, str):
                try:
                    parsed = json.loads(settings_raw)
                    settings = parsed if isinstance(parsed, dict) else {}
                except Exception:
                    settings = {}
            elif isinstance(settings_raw, dict):
                settings = settings_raw
            elif isinstance(settings_raw, list):
                settings = {}
            else:
                settings = {}

            changed = False
            for name, _, _, default, _ in DEFAULT_USER_SETTINGS:
                if name not in settings:
                    settings[name] = default
                    changed = True

            if changed:
                await conn.execute(
                    "UPDATE global_users SET settings = $1::jsonb WHERE user_id = $2",
                    json.dumps(settings, ensure_ascii=False),
                    user_id,
                )

    async def get_user_setting(self, user_id: int, name: str):
        """
        Получает значение глобальной пользовательской настройки.

        Если запись пользователя отсутствует — создаёт её. Если ключ отсутствует — возвращает значение по умолчанию из DEFAULT_USER_SETTINGS.
        """
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                await self.add_global_user(user_id)
                await self.init_user_settings(user_id)
                for setting_name, _, _, default, _ in DEFAULT_USER_SETTINGS:
                    if setting_name == name:
                        return default
                return None

            settings_raw = row.get("settings")

            # Приведение к dict
            if settings_raw is None:
                settings = {}
            elif isinstance(settings_raw, str):
                try:
                    parsed = json.loads(settings_raw)
                    settings = parsed if isinstance(parsed, dict) else {}
                except Exception:
                    settings = {}
            elif isinstance(settings_raw, dict):
                settings = settings_raw
            elif isinstance(settings_raw, list):
                settings = {}
            else:
                settings = {}

            if name in settings:
                return settings[name]

            for setting_name, _, _, default, _ in DEFAULT_USER_SETTINGS:
                if setting_name == name:
                    return default

            return None

    async def set_user_setting(self, user_id: int, name: str, value):
        """Устанавливает значение глобальной пользовательской настройки в поле global_users.settings"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                await self.add_global_user(user_id)
                settings = {}
            else:
                settings_raw = row.get("settings")
                if settings_raw is None:
                    settings = {}
                elif isinstance(settings_raw, str):
                    try:
                        parsed = json.loads(settings_raw)
                        settings = parsed if isinstance(parsed, dict) else {}
                    except Exception:
                        settings = {}
                elif isinstance(settings_raw, dict):
                    settings = settings_raw
                elif isinstance(settings_raw, list):
                    settings = {}
                else:
                    settings = {}

            settings[name] = value

            await conn.execute(
                "UPDATE global_users SET settings = $1::jsonb WHERE user_id = $2",
                json.dumps(settings, ensure_ascii=False),
                user_id,
            )

    async def is_user_setting_exists(self, user_id: int, name: str) -> bool:
        """Проверяет существование ключа настройки в глобальных настройках юзера"""
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT settings FROM global_users WHERE user_id = $1",
                user_id,
            )
            if not row:
                return False
            settings_raw = row.get("settings")
            if settings_raw is None:
                return False
            if isinstance(settings_raw, str):
                try:
                    parsed = json.loads(settings_raw)
                    return isinstance(parsed, dict) and (name in parsed)
                except Exception:
                    return False
            if isinstance(settings_raw, dict):
                return name in settings_raw
            return False

    async def is_user_setting_enabled(self, user_id: int, name: str) -> bool:
        value = await self.get_user_setting(user_id, name)
        return bool(value)

    async def toggle_user_setting(
        self, user_id: int, name: str, enable: bool = None
    ) -> bool:
        """Переключает значение глобальной настройки пользователя"""
        current = await self.get_user_setting(user_id, name)
        new_val = bool(enable) if enable is not None else not bool(current)
        await self.set_user_setting(user_id, name, new_val)
        return new_val
    
    # Опять же, можно сделать всё в один запрос но мне впадлу
    async def restore_user_settings(self, user_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute("""UPDATE global_users SET settings = NULL WHERE user_id = $1;""", user_id)
        await self.init_user_settings(user_id)
