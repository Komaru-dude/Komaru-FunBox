import logging
import os
import subprocess
import signal
import sys
import shutil
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.methods import DeleteWebhook
from bot.utils.aio_tools import fetch_json
from bot.utils.global_storage import known_models

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
from .handlers.text import text_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
token = os.getenv("BOT_API_TOKEN")
bot = Bot(token)
dp = Dispatcher()


async def fetch_models():
    try:
        data = await fetch_json("https://api.onlysq.ru/ai/models")
        models = data.get("models", {})
        known_models.clear()
        known_models.update(
            {
                k: v
                for k, v in models.items()
                if v.get("modality") == "text" and v.get("status") == "work"
            }
        )
        logging.info(f"Загружено {len(known_models)} моделей")
    except Exception as e:
        logging.error(f"Не удалось загрузить модели: {e}")


def clear_cache():
    """Очищает папку cache относительно расположения бота."""
    try:
        bot_dir = Path(__file__).resolve().parent
        cache_dir = bot_dir / "cache"

        logging.info(f"Рассчитываем путь к кэшу: {cache_dir}")

        # Если папка существует - удаляем
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logging.info("Папка кэша удалена.")

        # Создаем папку, если отсутствует
        cache_dir.mkdir(parents=True, exist_ok=True)
        logging.info("Кэш успешно очищен!")

    except Exception as e:
        logging.error(f"Ошибка очистки кэша: {str(e)}", exc_info=True)


async def main():
    clear_cache()
    await fetch_models()

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
            "127.0.0.1",
            "--port",
            "8001",
        ],
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0),
    )

    try:
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

