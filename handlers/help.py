from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

help_router = Router()

@help_router.message(Command("help"))
async def cmd_help(message: Message):
    text = message.text.strip()
    parts = text.split()

    if len(parts) > 1:
        argument = parts[1].lower()  # Приводим к нижнему регистру для удобства
        if argument == "new_year":
            await message.reply("Данная команда позволяет узнать время для нового года.\n"
                                "Команда в качестве аргумента принимает 'krsk' - будет использованно красноярское время.")
        elif argument == "birthdays":
            await message.reply("Данная команда позволяет узнать когда деньрождения у множества кошек.\n"
                                "Команда в качестве аргумента принимает 'krsk' - будет использованно красноярское время")
        elif argument == "random":
            await message.reply("Выводит рандомный ответ на ваш вопрос.")
        else:
            await message.reply("Какие команды есть в боте:\n"
                                "/start - Базовая команда, выступает заглушкой\n"
                                "/new_year - Время до нового года\n"
                                "/birthdays - Время до дня рождения кошек\n"
                                "/random - Рандомный ответ на ваш вопрос\n\n"
                                "Если хотите подробно узнать о каждой из команд используйте: /help <команда>")
    else:
        await message.reply("Какие команды есть в боте:\n"
                            "/start - Базовая команда, выступает заглушкой\n"
                            "/new_year - Время до нового года\n"
                            "/birthdays - Время до дня рождения кошек\n"
                            "/random - Рандомный ответ на ваш вопрос\n\n"
                            "Если хотите подробно узнать о каждой из команд используйте: /help <команда>")