import json

from aiogram import Bot, types

from bot import logger, COMMANDS_DIR


async def apply_all_command_sets(bot: Bot):
    for file in COMMANDS_DIR.glob("*.json"):
        language_code = file.stem  # конвертация в нормальный language_code

        with file.open("r", encoding="utf-8") as f:
            logger.debug(f"🔄 Загружаю файл: {f.name}")
            data = json.load(f)
            logger.debug(f"Тип data: {type(data)}, ключи: {list(data.keys())}")

        commands = [types.BotCommand(**cmd) for cmd in data["commands"]]

        # При имени файла default язык не указываем
        lang = None if language_code == "default" else language_code

        await bot.set_my_commands(commands=commands, language_code=lang)
        logger.debug(f"✅ Установлены команды для языка '{language_code}'")
