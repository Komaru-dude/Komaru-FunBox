import asyncio, logging, os, subprocess, signal, sys
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from .handlers.basic import base_router
from .handlers.time import time_router
from .handlers.help import help_router
from .handlers.rp import rp_router
from .handlers.ai import ai_router
from .handlers.mods import mods_router
from .handlers.text import text_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
token = os.getenv("BOT_API_TOKEN")
bot = Bot(token)
dp = Dispatcher()

if sys.platform == 'win32':
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    dp.include_routers(base_router, time_router, help_router, rp_router, ai_router, mods_router, text_router)
    pyrogram_process = subprocess.Popen(["uvicorn", "bot.utils.pyro_tools:server", "--host", "127.0.0.1", "--port", "8001"])

    try:
        await dp.start_polling(bot)
    finally:
        await bot.close()
        pyrogram_process.send_signal(signal.SIGTERM)
        pyrogram_process.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Основной процесс завершен.")
