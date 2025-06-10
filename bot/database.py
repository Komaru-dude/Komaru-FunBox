import asyncio, asyncpg, os, time, random, json, logging, time
from pathlib import Path
from dotenv import load_dotenv
from datetime import date, timedelta

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
    ("senddisabledmsg", 1),
    ("alo", 0),
    ("sendcooldown", 1),
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

FEATURES_COLUMNS = {
    "chat_id": "BIGINT",
    "feature_name": "TEXT",
    "is_enabled": "BOOLEAN DEFAULT FALSE",
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
}

COMMAND_COOLDOWNS_COLUMNS = {
    "user_id": "BIGINT NOT NULL",
    "chat_id": "BIGINT NOT NULL",
    "command": "TEXT NOT NULL",
    "available_at": "BIGINT NOT NULL",
}

USES_COLUMNS = {"count": "INTEGER NOT NULL DEFAULT 0"}

ECONOMY_COLUMNS = {
    "currency_sign": "TEXT DEFAULT '🪙'",
    "min_work_income": "INTEGER DEFAULT 20",
    "max_work_income": "INTEGER DEFAULT 250",
    "work_timeout": "INTEGER DEFAULT 14400",  # 4 часа
    "min_steal_income": "INTEGER DEFAULT 50",
    "max_steal_income": "INTEGER DEFAULT 400",
    "min_steal_penalty": "INTEGER DEFAULT 100",
    "max_steal_penalty": "INTEGER DEFAULT 600",
    "steal_fail_percent": "INTEGER DEFAULT 30",
    "steal_timeout": "INTEGER DEFAULT 21600",  # 6 часов
    "rob_min_percent": "INTEGER DEFAULT 5",
    "rob_max_percent": "INTEGER DEFAULT 15",
    "rob_fail_percent": "INTEGER DEFAULT 55",
    "rob_timeout": "INTEGER DEFAULT 28800",  # 8 часов
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
                # Таблица users
                users_def = ",\n".join(
                    [f"{col} {definition}" for col, definition in USERS_COLUMNS.items()]
                )
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS users (
                        {users_def},
                        PRIMARY KEY (user_id, chat_id)
                    )
                    """
                )

                # Таблица features
                features_def = ",\n".join(
                    [
                        f"{col} {definition}"
                        for col, definition in FEATURES_COLUMNS.items()
                    ]
                )
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS features (
                        {features_def},
                        PRIMARY KEY (chat_id, feature_name)
                    )
                    """
                )

                # Таблица banned_users
                banned_users_def = ",\n".join(
                    [
                        f"{col} {definition}"
                        for col, definition in BANNED_USERS_COLUMNS.items()
                    ]
                )
                await conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS banned_users (
                        {banned_users_def}
                    )
                    """
                )

                # Таблица chats
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS chats (
                        {", ".join([f"{k} {v}" for k, v in CHATS_COLUMNS.items()])}
                    )"""
                )

                # Таблица global_users
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS global_users (
                        {", ".join([f"{k} {v}" for k, v in GLOBAL_USERS_COLUMNS.items()])}
                    )"""
                )

                # Таблица command_cooldowns
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS command_cooldowns (
                        {", ".join([f"{k} {v}" for k, v in COMMAND_COOLDOWNS_COLUMNS.items()])},
                        PRIMARY KEY (user_id, chat_id, command)
                    )"""
                )

                # Таблица uses
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS uses (
                        day DATE PRIMARY KEY,
                        {", ".join([f"{k} {v}" for k, v in USES_COLUMNS.items()])}
                    )"""
                )

                # Таблица economy
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS economy (
                        {", ".join([f"{k} {v}" for k, v in ECONOMY_COLUMNS.items()])}
                    )"""
                )

                # Добавляем недостающие столбцы в users
                users_existing_cols = await conn.fetch(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'users'
                    """
                )
                users_existing_col_names = {
                    r["column_name"] for r in users_existing_cols
                }

                for col, definition in USERS_COLUMNS.items():
                    if col not in users_existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE users ADD COLUMN {col} {definition}"""
                        )

                # Добавляем недостающие столбцы в chats
                chats_existing_cols = await conn.fetch(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'chats'
                    """
                )
                chats_existing_col_names = {
                    r["column_name"] for r in chats_existing_cols
                }

                for col, definition in CHATS_COLUMNS.items():
                    if col not in chats_existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE chats ADD COLUMN {col} {definition}"""
                        )

                # Добавляем недостающие столбцы в global_users
                globusers_existing_cols = await conn.fetch(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'global_users'
                    """
                )
                globusers_existing_col_names = {
                    r["column_name"] for r in globusers_existing_cols
                }

                for col, definition in GLOBAL_USERS_COLUMNS.items():
                    if col not in globusers_existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE global_users ADD COLUMN {col} {definition}"""
                        )

                # Добавляем недостающие столбцы в uses
                uses_existing_cols = await conn.fetch(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'uses'
                    """
                )
                uses_existing_col_names = {r["column_name"] for r in uses_existing_cols}

                for col, definition in USES_COLUMNS.items():
                    if col not in uses_existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE uses ADD COLUMN {col} {definition}"""
                        )

                # Добавляем недостающие столбцы в economy
                eco_existing_cols = await conn.fetch(
                    """SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'economy'
                    """
                )
                eco_existing_col_names = {r["column_name"] for r in eco_existing_cols}

                for col, definition in ECONOMY_COLUMNS.items():
                    if col not in eco_existing_col_names:
                        await conn.execute(
                            f"""ALTER TABLE economy ADD COLUMN {col} {definition}"""
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

    async def toggle_feature(
        self, chat_id: int, feature_name: str, enable: bool = False
    ):
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

    # Функции для совместимости, в будущем будут убраны
    async def update_user_warns(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "warn", reason)

    async def update_user_mutes(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "mute", reason)

    async def update_user_bans(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "ban", reason)

    async def update_user_warn_limit(self, user_id: int, chat_id: int, warn_limit: int):
        await self.set_user_param(user_id, chat_id, "warn_limit", warn_limit)

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
                user_data.get("language_code", "en") if user_data is not None else "en"
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
                """SELECT * FROM users WHERE user_id = $1""",
                user_id,
            )
            if not row:
                await self.add_global_user(user_id)
                row = await conn.fetchrow(
                    """SELECT * FROM users WHERE user_id = $1""",
                    user_id,
                )
                if not row:
                    return {}
            return row.get(param)

    async def set_global_user_param(self, user_id: int, param: str, value):
        """Устанавливает параметр пользователю глобально"""
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
        chat_id: int,
        command: str,
        cooldown: int,
    ) -> bool:
        """
        Проверяет, доступна ли команда. Если доступна устанавливает новый кулдаун.

        :param user_id: ID пользователя
        :param chat_id: ID чата
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
                WHERE user_id = $1 AND chat_id = $2 AND command = $3
                """,
                user_id,
                chat_id,
                command,
            )

            if row and row["available_at"] > now:
                return False  # Кулдаун активен

            new_available_at = now + cooldown

            if row:
                await conn.execute(
                    """
                    UPDATE command_cooldowns
                    SET available_at = $4
                    WHERE user_id = $1 AND chat_id = $2 AND command = $3
                    """,
                    user_id,
                    chat_id,
                    command,
                    new_available_at,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO command_cooldowns (user_id, chat_id, command, available_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    user_id,
                    chat_id,
                    command,
                    new_available_at,
                )

            return True

    async def get_cooldown_remaining(
        self,
        user_id: int,
        chat_id: int,
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
                WHERE user_id = $1 AND chat_id = $2 AND command = $3
                """,
                user_id,
                chat_id,
                command,
            )
            if row:
                return max(0, row["available_at"] - now)
            return 0

    async def reset_cooldown(
        self,
        user_id: int,
        chat_id: int,
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
                WHERE user_id = $1 AND chat_id = $2 AND command = $3
                """,
                user_id,
                chat_id,
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
