import asyncio, asyncpg, os, time, random, json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

RANK_TO_LEVEL = {
    "Участник": 0,
    "Модератор": 1,
    "Администратор": 2,
    "Владелец": 3,
    "Персонал": 4,
}

DEFAULT_FEATURES = [
    ("who", 1),
    ("tag", 0),
    ("autovideo", 1),
    ("warn", 0),
    ("mute", 0),
    ("ban", 0),
    ("SendDisabledMsg", 1)
]

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
    "warn_limit": "INTEGER DEFAULT 3",
    "default_model": "TEXT DEFAULT ''",
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
                logging.info("Уже подключены к БД.")
                return

            try:
                logging.info("Подключаемся к базе данных...")
                if self.pool and not self.pool.is_closing():
                    await self.pool.close()
                    logging.info("Существующий пул был закрыт перед переподключением.")

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
                logging.info("Пул соединений с БД успешно создан.")

                await self.create_tables()
                await self.sync_all()
                logging.info("Успешное подключение и синхронизация с БД.")

            except Exception as e:
                logging.critical(
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
                # Формируем SQL из USERS_COLUMNS
                columns_def = ",\n".join(
                    [f"{col} {definition}" for col, definition in USERS_COLUMNS.items()]
                )
                primary_keys = "PRIMARY KEY (user_id, chat_id)"

                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS users (
                        {columns_def},
                        {primary_keys}
                    )
                    """
                )

                # Таблица фич
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS features (
                        chat_id BIGINT,
                        feature_name TEXT,
                        is_enabled BOOLEAN DEFAULT FALSE,
                        PRIMARY KEY (chat_id, feature_name)
                    )
                    """
                )

                # Таблица заблокированных
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS banned_users (
                        user_id BIGINT PRIMARY KEY
                    )
                    """
                )

                # Добавляем недостающие столбцы в users
                existing_cols = await conn.fetch(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users'
                    """
                )
                existing_col_names = {r["column_name"] for r in existing_cols}

                for col, definition in USERS_COLUMNS.items():
                    if col not in existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE users ADD COLUMN {col} {definition}"""
                        )

    async def sync_all(self):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Синхронизируем фичи
                chat_ids_records = await conn.fetch(
                    "SELECT DISTINCT chat_id FROM features"
                )
                chat_ids = [r["chat_id"] for r in chat_ids_records]
                for chat_id_val in chat_ids:
                    # Добавляем отсутствующие фичи
                    for feature, enabled in DEFAULT_FEATURES:
                        await conn.execute(
                            """
                            INSERT INTO features (chat_id, feature_name, is_enabled)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (chat_id, feature_name) DO NOTHING
                        """,
                            chat_id_val,
                            feature,
                            bool(enabled),
                        )

                    # Удаляем старые фичи
                    feature_names = [f[0] for f in DEFAULT_FEATURES]
                    await conn.execute(
                        """
                        DELETE FROM features 
                        WHERE chat_id = $1 
                        AND feature_name NOT IN (SELECT unnest($2::text[]))
                    """,
                        chat_id_val,
                        feature_names,
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

    async def init_chat_features(self, chat_id: int):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            for feature, enabled in DEFAULT_FEATURES:
                await conn.execute(
                    """
                    INSERT INTO features (chat_id, feature_name, is_enabled)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                """,
                    chat_id,
                    feature,
                    bool(enabled),
                )

    async def is_feature_exists(self, chat_id: int, feature_name: str) -> bool:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM features 
                    WHERE chat_id = $1 AND feature_name = $2
                )
            """,
                chat_id,
                feature_name,
            )

    async def is_feature_enabled(self, chat_id: int, feature_name: str) -> bool:
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT is_enabled FROM features 
                WHERE chat_id = $1 AND feature_name = $2
            """,
                chat_id,
                feature_name,
            )

    async def toggle_feature(self, chat_id: int, feature_name: str, enable: bool):
        await self.ensure_connection()
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE features 
                SET is_enabled = $1 
                WHERE chat_id = $2 AND feature_name = $3
            """,
                enable,
                chat_id,
                feature_name,
            )

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
            value = random.randint(1, 6)

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

    async def update_user_warns(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "warn", reason)

    async def update_user_mutes(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "mute", reason)

    async def update_user_bans(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "ban", reason)

    async def update_user_warn_limit(self, user_id: int, chat_id: int, warn_limit: int):
        await self.set_user_param(user_id, chat_id, "warn_limit", warn_limit)
