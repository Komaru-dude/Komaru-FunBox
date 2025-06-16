import asyncio
import os
import subprocess
import signal
import sys
import shutil
import json
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.methods import DeleteWebhook

from bot import PYRO_HOST, PYRO_PORT, logger
from bot.database import BASE_DIR, Database
from bot.middlewares.specificchat import SpecificChat
from bot.middlewares.chatwatcher import ChatWatcher
from bot.utils.global_storage import onlysq_models
from bot.utils.aio_tools import fetch_json
from bot.utils.update_checker import background_update_checker

from .handlers.basic import base_router
from .handlers.etc import etc_router
from .handlers.time import time_router
from .handlers.help import help_router
from .handlers.rp import rp_router
from .handlers.ai import ai_router
from .handlers.mods import mods_router
from .handlers.rights import rights_router
from .handlers.tag import tag_router
from .handlers.video import video_router
from .handlers.image import image_router
from .handlers.economy import eco_router
from .handlers.text import text_router

load_dotenv()

token = os.getenv("BOT_API_TOKEN")
bot = Bot(token)
dp = Dispatcher()
dp.message.outer_middleware(ChatWatcher())
dp.message.outer_middleware(SpecificChat())
db = Database()
dp["db"] = db
DATA_DIR = BASE_DIR / "data"


async def load_models():
    models_path = DATA_DIR / "models.json"
    default_models = {"models": {}}

    try:
        if not models_path.exists():
            logger.info("Модели отсутствуют, загружаю с API...")
            try:
                models = await fetch_json("https://api.onlysq.ru/ai/models")

                if not isinstance(models, dict) or not isinstance(
                    models.get("models"), dict
                ):
                    raise ValueError("API вернул некорректный формат моделей")

                with open(models_path, "w") as f:
                    json.dump(models, f, indent=2)

                onlysq_models.clear()
                onlysq_models.update(models)
                logger.info(f"Успешно загружено {len(models['models'])} моделей")
                return

            except Exception as e:
                logger.error(f"Ошибка загрузки с API: {e}")
                onlysq_models.update(default_models)
                return

        with open(models_path, "r") as f:
            cached_models = json.load(f)

            if not isinstance(cached_models, dict) or not isinstance(
                cached_models.get("models"), dict
            ):
                raise ValueError("Поврежденный кэш моделей")

            onlysq_models.clear()
            onlysq_models.update(cached_models)
            logger.info(f"Загружено {len(cached_models['models'])} моделей из кэша")

    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.error(f"Критическая ошибка загрузки: {e}")
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

        logger.info(f"Рассчитываем путь к кэшу: {cache_dir}")

        # Если папка существует - удаляем
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info("Папка кэша удалена.")

        # Создаем папку, если отсутствует
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Кэш успешно очищен!")

    except Exception as e:
        logger.error(f"Ошибка очистки кэша: {str(e)}", exc_info=True)


async def main():
    clear_cache()
    await load_models()
    await db.connect()

    dp.include_routers(
        base_router,
        etc_router,
        time_router,
        help_router,
        rp_router,
        ai_router,
        mods_router,
        rights_router,
        tag_router,
        video_router,
        image_router,
        eco_router,
        text_router,
    )

    uvicorn_exec = (
        Path(sys.prefix) / "Scripts" / "uvicorn.exe"
        if sys.platform == "win32"
        else Path(sys.prefix) / "bin" / "uvicorn"
    )
    pyrogram_process = subprocess.Popen(
        [
            uvicorn_exec,
            "bot.utils.pyro_tools:server",
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
        asyncio.create_task(background_update_checker())
        await bot(DeleteWebhook(drop_pending_updates=True))
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if pyrogram_process.poll() is None:
            if sys.platform == "win32":
                pyrogram_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                pyrogram_process.send_signal(signal.SIGTERM)
            try:
                pyrogram_process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                pyrogram_process.kill()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Основной процесс завершён.")
