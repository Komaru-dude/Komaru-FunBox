import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from traceback import format_exc

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import PRODUCTION, TEST
from aiogram.methods import DeleteWebhook

from bot import DATA_DIR, IS_TEST, IS_TEST_ENV, PYRO_HOST, PYRO_PORT, logger
from bot.database.database import Database
from bot.database.redis_client import redis_db
from bot.middlewares.chatwatcher import ChatWatcher
from bot.middlewares.specificchat import SpecificChat
from bot.utils.ai_api import check_models
from bot.utils.bot_tools import download_osq_models
from bot.utils.cmd_manager import apply_all_command_sets
from bot.utils.global_storage import onlysq_models
from bot.utils.timers import background_checker

from .handlers.administration import admin_router
from .handlers.ai.ai import ai_router
from .handlers.ai.image import image_router
from .handlers.ai.prompts import prompts_router
from .handlers.basic import base_router
from .handlers.economy.eco_invest import invest_router
from .handlers.economy.economy import eco_router
from .handlers.etc import etc_router
from .handlers.mods import mods_router
from .handlers.premium import premium_router
from .handlers.rights import rights_router
from .handlers.rp import rp_router
from .handlers.service import service_router
from .handlers.settings import settings_router
from .handlers.text import text_router
from .handlers.user_settings import usettings_router
from .handlers.video import video_router

# TODO: Возможно излишнее кол-во тестовых переменных, глянуть потом
if IS_TEST_ENV:
    token = os.getenv("TEST_BOT_API_TOKEN") or sys.exit(1)
else:
    token = os.getenv("BOT_API_TOKEN") or sys.exit(1)

if IS_TEST_ENV:
    session = AiohttpSession(api=TEST)
    bot = Bot(token=token, session=session)
    logger.debug(f"🧪 Используется тестовый API сервер: {token}")
else:
    bot = Bot(token=token, server=PRODUCTION)

dp = Dispatcher()
dp.message.outer_middleware(ChatWatcher())
dp.callback_query.outer_middleware(ChatWatcher())
dp.message.outer_middleware(SpecificChat())
db = Database()
dp["db"] = db
redis_port = int(os.getenv("REDIS_PORT", 6379))


async def load_models():
    models_path = DATA_DIR / "models.json"
    default_models = {"models": {}}

    try:
        if not models_path.exists():
            logger.info("🔄 Модели отсутствуют, загружаю с API...")
            await download_osq_models()

        with open(models_path, "r") as f:
            cached_models = json.load(f)

            if not isinstance(cached_models, dict) or not isinstance(
                cached_models.get("models"), dict
            ):
                raise ValueError("📛 Поврежденный кэш моделей")

            onlysq_models.clear()
            onlysq_models.update(cached_models)
            logger.info(f"✅ Загружено {len(cached_models['models'])} моделей из кэша")

    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.error(f"📛 Критическая ошибка загрузки: {e}")
        onlysq_models.update(default_models)
        models_path.unlink(missing_ok=True)

    except Exception as e:
        logger.critical(f"Непредвиденная ошибка: {e}")
        onlysq_models.update(default_models)
        raise


def clear_cache():
    """Очищает папку cache относительно расположения бота."""
    try:
        bot_dir = Path(__file__).resolve().parent
        cache_dir = bot_dir / "cache"

        logger.info(f"🕐 Рассчитываем путь к кэшу: {cache_dir}")

        # Если папка существует - удаляем
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

        # Создаем папку, если отсутствует
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("🧼 Кэш успешно очищен!")

    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {str(e)}", exc_info=True)


async def main():
    try:
        logger.info("🍕 Komaru FunBox")
        if IS_TEST:
            logger.debug("🧑‍💻 Используется тестовая ветка")
        logger.info("▶️ Подготовка...")
        clear_cache()
        await load_models()
        await db.connect()
        await redis_db.connect(port=redis_port)
        await check_models(include_image=True)
        await apply_all_command_sets(bot)
    except Exception:
        logger.fatal(
            f"📛 Не удалось выполнить подготовку.\n\nTraceback: {format_exc()}"
        )

    dp.include_routers(
        admin_router,
        base_router,
        etc_router,
        rp_router,
        ai_router,
        mods_router,
        prompts_router,
        image_router,
        settings_router,
        usettings_router,
        service_router,
        rights_router,
        video_router,
        eco_router,
        invest_router,
        premium_router,
        text_router,
    )

    uvicorn_exec = (
        Path(sys.prefix) / "Scripts" / "uvicorn.exe"
        if sys.platform == "win32"
        else Path(sys.prefix) / "bin" / "uvicorn"
    )
    telethon_process = subprocess.Popen(
        [
            uvicorn_exec,
            "bot.utils.tele_tools:server",
            "--host",
            PYRO_HOST,
            "--port",
            str(PYRO_PORT),
        ],
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
        ),
    )

    try:
        asyncio.create_task(background_checker(bot))
        await bot(DeleteWebhook(drop_pending_updates=True))
        await dp.start_polling(
            bot, allowed_updates=["message", "callback_query", "my_chat_member"]
        )
    except Exception:
        logger.fatal(f"📛 Запуск не удался.\n\nTraceback: {format_exc()}")
    finally:
        await bot.session.close()
        await redis_db.close()
        if telethon_process.poll() is None:
            if sys.platform == "win32":
                telethon_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                telethon_process.send_signal(signal.SIGTERM)
            try:
                telethon_process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                telethon_process.kill()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🤔 Основной процесс завершён.")
