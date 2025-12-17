import asyncio
import os
from typing import Any, Optional

import asyncpg
from asyncpg import Pool

from bot import logger
from bot.database.bootstrap import create_tables as bootstrap_create_tables
from bot.database.bootstrap import sync_all as bootstrap_sync_all
from bot.database.logic import (
    active_users,
    admin,
    chats,
    economy,
    prompts,
    settings,
    users,
    utils,
)


class Database:
    def __init__(self):
        self.pool: Optional[Pool] = None
        self.owner_id = int(os.getenv("OWNER_ID", 0))
        self._lock = asyncio.Lock()
        self.is_connected = False

    async def ensure_connection(self) -> Pool:
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

    # Юзеры и ранги

    async def user_exists(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.exists(pool, user_id, chat_id)

    async def add_user(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        await users.create(pool, user_id, chat_id)

    async def get_user_data(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.get_full_data(pool, user_id, chat_id)

    async def get_global_user(self, user_id: int):
        pool = await self.ensure_connection()
        return await users.get_global_data(pool, user_id)

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

    async def get_user_param(self, user_id: int, chat_id: int, param: str):
        pool = await self.ensure_connection()
        return await users.get_user_param(pool, user_id, chat_id, param)

    async def set_user_param(self, user_id: int, chat_id: int, param: str, value):
        pool = await self.ensure_connection()
        await users.set_user_param(pool, user_id, chat_id, param, value)

    async def update_user_history(
        self, user_id: int, chat_id: int, punishment_type: str, reason: str
    ):
        pool = await self.ensure_connection()
        await users.add_history_record(pool, user_id, chat_id, punishment_type, reason)

    async def get_user_history(self, user_id: int, chat_id: int):
        pool = await self.ensure_connection()
        return await users.get_history(pool, user_id, chat_id)

    # Активные юзеры

    async def add_active_user(self, user_id: int):
        pool = await self.ensure_connection()
        await active_users.add_active_user(pool, user_id)

    async def delete_active_user(self, user_id: int):
        pool = await self.ensure_connection()
        await active_users.delete_active_user(pool, user_id)

    async def is_active_user(self, user_id: int):
        pool = await self.ensure_connection()
        return await active_users.is_active_user(pool, user_id)

    async def get_active_users_count(self):
        pool = await self.ensure_connection()
        return await active_users.get_active_users_count(pool)

    # Чаты

    async def add_chat(self, chat_id: int, chat_type: str = "private"):
        pool = await self.ensure_connection()
        await chats.add_chat(pool, chat_id, chat_type)

    async def get_chat(self, chat_id: int):
        pool = await self.ensure_connection()
        return await chats.get_chat(pool, chat_id)

    async def chat_exists(self, chat_id: int):
        pool = await self.ensure_connection()
        return await chats.chat_exists(pool, chat_id)

    async def get_all_chats(self):
        pool = await self.ensure_connection()
        return await chats.get_all_chats(pool)

    # Настройки чата

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

    async def init_chat_settings(self, chat_id: int):
        pool = await self.ensure_connection()
        return await settings.init_chat_settings(pool, chat_id)

    async def restore_chat_settings(self, chat_id: int):
        pool = await self.ensure_connection()
        return await settings.restore_chat_settings(pool, chat_id)

    async def is_setting_exists(self, chat_id: int, name: str) -> bool:
        pool = await self.ensure_connection()
        return await settings.is_setting_exists(pool, chat_id, name)

    async def get_chats_with_setting(self, setting_name: str):
        pool = await self.ensure_connection()
        return await settings.get_chats_with_setting(pool, setting_name)

    # Настройки юзера

    async def get_user_setting(self, user_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.get_user_val(pool, user_id, name)

    async def set_user_setting(self, user_id: int, name: str, value: Any):
        pool = await self.ensure_connection()
        await settings.set_user_val(pool, user_id, name, value)

    async def init_user_settings(self, user_id: int):
        pool = await self.ensure_connection()
        await settings.init_user_settings(pool, user_id)

    async def restore_user_settings(self, user_id: int):
        pool = await self.ensure_connection()
        await settings.restore_user_settings(pool, user_id)

    async def is_user_setting_exists(self, user_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.is_user_setting_exists(pool, user_id, name)

    async def toggle_user_setting(
        self, user_id: int, name: str, enable: Optional[bool] = None
    ):
        pool = await self.ensure_connection()
        return await settings.toggle_user_setting(pool, user_id, name, enable)

    async def is_user_setting_enabled(self, user_id: int, name: str):
        pool = await self.ensure_connection()
        return await settings.is_user_setting_enabled(pool, user_id, name)

    # Экономика

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

    async def cleanup_all_expired_items(self):
        pool = await self.ensure_connection()
        await economy.cleanup_all_expired_items(pool)

    # Баны

    async def mediaban_user(self, user_id: int):
        pool = await self.ensure_connection()
        await admin.ban_media(pool, user_id)

    async def unban_media_user(self, user_id: int):
        pool = await self.ensure_connection()
        await admin.unban_media(pool, user_id)

    async def is_user_mediabanned(self, user_id: int):
        pool = await self.ensure_connection()
        return await admin.check_media_ban(pool, user_id)

    # Промпты

    async def add_prompt(
        self, user_id: int, title: str, content: str, is_public: bool = False
    ):
        pool = await self.ensure_connection()
        return await prompts.create(pool, user_id, title, content, is_public)

    async def get_prompt(self, prompt_id: str):
        pool = await self.ensure_connection()
        return await prompts.get_by_id(pool, prompt_id)

    async def get_all_prompts(self, user_id: int):
        pool = await self.ensure_connection()
        return await prompts.get_all_prompts(pool, user_id)

    async def get_prompt_by_title(self, title: str, user_id: int):
        pool = await self.ensure_connection()
        return await prompts.get_prompt_by_title(pool, title, user_id)

    async def update_prompt(
        self,
        prompt_id: str,
        user_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        is_public: Optional[bool] = None,
    ):
        pool = await self.ensure_connection()
        return await prompts.update_prompt(
            pool, prompt_id, user_id, title, content, is_public
        )

    async def remove_prompt(self, prompt_id: str):
        pool = await self.ensure_connection()
        return await prompts.remove_prompt(pool, prompt_id)

    # Утилиты и кулдауны

    async def is_command_available(self, user_id: int, command: str, cooldown: int):
        pool = await self.ensure_connection()
        return await utils.check_cooldown(pool, user_id, command, cooldown)

    async def get_cooldown_remaining(self, user_id: int, command: str):
        pool = await self.ensure_connection()
        return await utils.get_cooldown_remaining(pool, user_id, command)

    async def reset_cooldown(self, user_id: int, command: str):
        pool = await self.ensure_connection()
        await utils.reset_cooldown(pool, user_id, command)

    async def log_command(self):
        pool = await self.ensure_connection()
        await utils.register_command_usage(pool)

    async def get_use_stats(self):
        pool = await self.ensure_connection()
        return await utils.get_usage_stats(pool)
