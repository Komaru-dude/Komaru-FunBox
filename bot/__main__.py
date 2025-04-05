import asyncio, logging, os, subprocess, signal
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from .handlers.start import strt_router
from .handlers.time import time_router
from .handlers.help import help_router
from .handlers.random import random_router
from .handlers.rp import rp_router
from .handlers.privet import pr_router
from .handlers.ai import ai_router
from .handlers.text import text_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
token = os.getenv("BOT_API_TOKEN")
bot = Bot(token)
dp = Dispatcher()

async def main():
    dp.include_routers(strt_router, time_router, help_router, random_router, rp_router, pr_router, ai_router, text_router)
    pyrogram_process = subprocess.Popen(["uvicorn", "bot.utils.pyro_tools:server", "--host", "127.0.0.1", "--port", "8001"])

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("Бот выключен")
    finally:
        await bot.close()
        pyrogram_process.send_signal(signal.SIGTERM)
        pyrogram_process.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Основной процесс завершен.")
