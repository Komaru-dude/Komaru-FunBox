import asyncio, logging, os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from handlers.start import strt_router
from handlers.time import time_router

load_dotenv()

# Включаем логирование, чтобы не пропустить важные сообщения
logging.basicConfig(level=logging.INFO)
# Объект бота
token = os.getenv("BOT_API_TOKEN")
bot = Bot(token)
# Диспетчер
dp = Dispatcher()

# Запуск процесса поллинга новых апдейтов
async def main():
    dp.include_routers(strt_router, time_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
