import asyncpg, os, time, random
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
]

class Database:
    def __init__(self):
        self.pool = None
        self.owner_id = int(os.getenv("OWNER_ID", 0))

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
        await self.create_tables()
        await self.sync_all()

    async def create_tables(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Таблица юзеров
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT,
                        chat_id BIGINT,
                        warns INTEGER DEFAULT 0,
                        bans INTEGER DEFAULT 0,
                        mutes INTEGER DEFAULT 0,
                        reputation INTEGER DEFAULT 0,
                        rank TEXT DEFAULT 'Участник',
                        message_count INTEGER DEFAULT 0,
                        history JSONB DEFAULT '[]'::JSONB,
                        warn_limit INTEGER DEFAULT 3,
                        first_name TEXT DEFAULT '',
                        PRIMARY KEY (user_id, chat_id)
                    )
                """)
                
                # Таблица фич
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS features (
                        chat_id BIGINT,
                        feature_name TEXT,
                        is_enabled BOOLEAN DEFAULT FALSE,
                        PRIMARY KEY (chat_id, feature_name)
                    )
                """)
                
                # Таблица заблокированных
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS banned_users (
                        user_id BIGINT PRIMARY KEY
                    )
                """)

    async def sync_all(self):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Синхронизируем фичи
                chat_ids = await conn.fetch("SELECT DISTINCT chat_id FROM features")
                for chat_id in [r['chat_id'] for r in chat_ids]:
                    # Добавляем отсутствующие фичи
                    for feature, enabled in DEFAULT_FEATURES:
                        await conn.execute("""
                            INSERT INTO features (chat_id, feature_name, is_enabled)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (chat_id, feature_name) DO NOTHING
                        """, chat_id, feature, bool(enabled))
                    
                    # Удаляем старые фичи
                    feature_names = [f[0] for f in DEFAULT_FEATURES]
                    await conn.execute("""
                        DELETE FROM features 
                        WHERE chat_id = $1 
                        AND feature_name NOT IN (SELECT unnest($2::text[]))
                    """, chat_id, feature_names)

    async def has_permission(self, user_id: int, chat_id: int, required_level: int) -> bool:
        if user_id == self.owner_id:
            return True

        async with self.pool.acquire() as conn:
            rank = await conn.fetchval("""
                SELECT rank FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id)
            
        return RANK_TO_LEVEL.get(rank, -1) >= required_level

    async def set_rank(self, user_id: int, chat_id: int, rank: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, chat_id, rank)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, chat_id) 
                DO UPDATE SET rank = EXCLUDED.rank
            """, user_id, chat_id, rank)

    async def user_exists(self, user_id: int, chat_id: int) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM users 
                    WHERE user_id = $1 AND chat_id = $2
                )
            """, user_id, chat_id)

    async def add_user(self, user_id: int, chat_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, chat_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, user_id, chat_id)

    async def get_user_rank(self, user_id: int, chat_id: int) -> str:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT rank FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id)

    async def update_message_count(self, user_id: int, chat_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users 
                SET message_count = message_count + 1 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id)

    async def get_user_data(self, user_id: int, chat_id: int) -> dict:
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow("""
                SELECT * FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id)
            
            if not record:
                await self.add_user(user_id, chat_id)
                return await self.get_user_data(user_id, chat_id)
            
            return dict(record)

    async def set_user_param(self, user_id: int, chat_id: int, param: str, value):
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE users 
                SET {param} = $1 
                WHERE user_id = $2 AND chat_id = $3
            """, value, user_id, chat_id)

    async def init_chat_features(self, chat_id: int):
        async with self.pool.acquire() as conn:
            for feature, enabled in DEFAULT_FEATURES:
                await conn.execute("""
                    INSERT INTO features (chat_id, feature_name, is_enabled)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                """, chat_id, feature, bool(enabled))

    async def is_feature_exists(self, chat_id: int, feature_name: str) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM features 
                    WHERE chat_id = $1 AND feature_name = $2
                )
            """, chat_id, feature_name)

    async def is_feature_enabled(self, chat_id: int, feature_name: str) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT is_enabled FROM features 
                WHERE chat_id = $1 AND feature_name = $2
            """, chat_id, feature_name)

    async def toggle_feature(self, chat_id: int, feature_name: str, enable: bool):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE features 
                SET is_enabled = $1 
                WHERE chat_id = $2 AND feature_name = $3
            """, enable, chat_id, feature_name)

    async def mediaban_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO banned_users (user_id)
                VALUES ($1)
                ON CONFLICT DO NOTHING
            """, user_id)

    async def mediaunban_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM banned_users 
                WHERE user_id = $1
            """, user_id)

    async def is_user_mediabanned(self, user_id: int) -> bool:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM banned_users 
                    WHERE user_id = $1
                )
            """, user_id)

    async def update_user_history(self, user_id: int, chat_id: int, punishment_type: str, reason: str):
        async with self.pool.acquire() as conn:
            history = await conn.fetchval("""
                SELECT history FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id) or []

            punishment = {
                "type": punishment_type,
                "reason": reason,
                "timestamp": int(time.time())
            }
            
            await conn.execute("""
                UPDATE users 
                SET 
                    history = $1,
                    {0} = {0} + 1 
                WHERE user_id = $2 AND chat_id = $3
            """.format(f"{punishment_type}s"), 
            history + [punishment], user_id, chat_id)

    async def get_user_history(self, user_id: int, chat_id: int) -> list:
        async with self.pool.acquire() as conn:
            history = await conn.fetchval("""
                SELECT history FROM users 
                WHERE user_id = $1 AND chat_id = $2
            """, user_id, chat_id)
            return history or []

    async def update_reputation(self, user_id: int, chat_id: int, mode: str, value: int = None):
        if mode not in ["auto_add", "manual_add", "manual_rem"]:
            raise ValueError("Invalid mode")

        if mode == "auto_add":
            value = random.randint(1, 6)

        async with self.pool.acquire() as conn:
            if mode in ["auto_add", "manual_add"]:
                await conn.execute("""
                    UPDATE users 
                    SET reputation = reputation + $1 
                    WHERE user_id = $2 AND chat_id = $3
                """, value, user_id, chat_id)
            elif mode == "manual_rem":
                await conn.execute("""
                    UPDATE users 
                    SET reputation = reputation - $1 
                    WHERE user_id = $2 AND chat_id = $3
                """, value, user_id, chat_id)

    async def update_user_warns(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "warn", reason)

    async def update_user_bans(self, user_id: int, chat_id: int, reason: str):
        await self.update_user_history(user_id, chat_id, "ban", reason)

    async def update_user_warn_limit(self, user_id: int, chat_id: int, warn_limit: int):
        await self.set_user_param(user_id, chat_id, "warn_limit", warn_limit)