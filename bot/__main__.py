import asyncio
import logging
import os
import subprocess
import signal
import sys
from pathlib import Path
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

async def main():
    dp.include_routers(
        base_router,
        time_router,
        help_router,
        rp_router,
        ai_router,
        mods_router,
        text_router
    )

    uvicorn_exec = Path(sys.prefix) / 'Scripts' / 'uvicorn.exe' if sys.platform == 'win32' else Path(sys.prefix) / 'bin' / 'uvicorn'
    pyrogram_process = subprocess.Popen(
        [uvicorn_exec, "bot.utils.pyro_tools:server", "--host", "127.0.0.1", "--port", "8001"],
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    )

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if pyrogram_process.poll() is None:
            if sys.platform == 'win32':
                pyrogram_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                pyrogram_process.send_signal(signal.SIGTERM)
            try:
                pyrogram_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pyrogram_process.kill()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Основной процесс завершён.")