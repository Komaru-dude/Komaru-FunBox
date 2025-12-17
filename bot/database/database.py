import asyncio
import os
from typing import Any, Optional

import asyncpg
from asyncpg import Pool

from bot import logger
from bot.database.bootstrap import create_tables as bootstrap_create_tables
from bot.database.bootstrap import sync_all as bootstrap_sync_all
from bot.database.logic import admin, economy, prompts, settings, users, utils


class Database:
    def __init__(self):
        self.pool: Optional[Pool] = None
        self.owner_id = int(os.getenv("OWNER_ID", 0))
        self._lock = asyncio.Lock()
        self.is_connected = False

    async def ensure_connection(self) -> Pool:
        """
        Проверяет соединение и ВОЗВРАЩАЕТ пул.
        Это критически важно для типизации.
        """
        if not self.is_connected or self.pool is None or self.pool.is_closing():
            await self.connect()

        if self.pool is None:
            raise ConnectionError("Database pool could not be established.")

        return self.pool

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

                if self.pool:
                    await bootstrap_create_tables(self.pool)
                    await bootstrap_sync_all(self.pool)
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
        pool = await self.ensure_connection()
        await utils.init_tables(pool)

    async def sync_all(self):
        pool = await self.ensure_connection()
        await settings.sync_database_schema(pool)

    async def user_exists(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.exists(pool, user_id, chat_id)

    async def add_user(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        await users.create(pool, user_id, chat_id)

    async def get_user_data(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.get_full_data(pool, user_id, chat_id)

    async def get_user_rank(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.get_rank(pool, user_id, chat_id)

    async def set_rank(self, user_id: int, chat_id: int, rank: str):
        pool = await self.ensure_connection()
        await users.set_rank(pool, user_id, chat_id, rank)

    async def has_permission(self, user_id: int, chat_id: int, required_level: int):
        pool = await self.ensure_connection()
        return await users.check_permission(
            pool, self.owner_id, user_id, chat_id, required_level
        )

    async def update_message_count(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        await users.inc_message_count(pool, user_id, chat_id)

    async def update_reputation(
        self, user_id: int, chat_id: int, mode: str, value: int = 0
    ):
        pool = await self.ensure_connection()
        await users.modify_reputation(pool, user_id, chat_id, mode, value)

    async def update_user_history(
        self, user_id: int, chat_id: int, punishment_type: str, reason: str
    ):
        pool = await self.ensure_connection()
        await users.add_history_record(pool, user_id, chat_id, punishment_type, reason)

    async def get_user_history(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        await users.get_history(pool, user_id, chat_id)

    async def get_setting(self, chat_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.get_chat_val(pool, chat_id, name)

    async def set_setting(self, chat_id: int, name: str, value: Any):
        pool = await self.ensure_connection()
        await settings.set_chat_val(pool, chat_id, name, value)

    async def toggle_setting(
        self, chat_id: int, name: str, enable: Optional[bool] = None
    ):
        pool = await self.ensure_connection()
        return await settings.toggle_chat_val(pool, chat_id, name, enable)

    async def is_setting_enabled(self, chat_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.is_enabled(pool, chat_id, name)

    async def get_user_setting(self, user_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.get_user_val(pool, user_id, name)

    async def set_user_setting(self, user_id: int, name: str, value: Any):
        pool = await self.ensure_connection()
        await settings.set_user_val(pool, user_id, name, value)

    async def get_eco_top(self, limit: int = 10):
        pool = await self.ensure_connection()
        return await economy.get_top_list(pool, limit)

    async def add_item_to_user(self, user_id: int, shop_item: dict):
        pool = await self.ensure_connection()
        await economy.give_item(pool, user_id, shop_item)

    async def use_item(self, user_id: int, item_id: str):
        pool = await self.ensure_connection()
        return await economy.consume_item(pool, user_id, item_id)

    async def has_valid_item(self, user_id: int, item_id: str):
        pool = await self.ensure_connection()
        return await economy.check_item(pool, user_id, item_id)

    async def mediaban_user(self, user_id: int):
        pool = await self.ensure_connection()
        await admin.ban_media(pool, user_id)

    async def is_user_mediabanned(self, user_id: int):
        pool = await self.ensure_connection()
        return await admin.check_media_ban(pool, user_id)

    async def is_command_available(self, user_id: int, command: str, cooldown: int):
        pool = await self.ensure_connection()
        return await utils.check_cooldown(pool, user_id, command, cooldown)

    async def log_command(self):
        pool = await self.ensure_connection()
        await utils.register_command_usage(pool)

    async def add_prompt(
        self, user_id: int, title: str, content: str, is_public: bool = False
    ):
        pool = await self.ensure_connection()
        return await prompts.create(pool, user_id, title, content, is_public)

    async def get_prompt(self, prompt_id: str):
        pool = await self.ensure_connection()
        return await prompts.get_by_id(pool, prompt_id)
