from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

help_router = Router()

@help_router.message(Command("help"))
async def cmd_help(message: Message):
    short_descriptions = {
        "start": "Базовая команда, выступает заглушкой",
        "new_year": "Время до нового года",
        "birthdays": "Время до дня рождения кошек",
        "random": "Рандомный ответ на ваш вопрос",
        "help": "Не",
        "rp_setup": "Первично настроивает рп команды в вашем чате",
        "rp_add": "Добавляет новую рп команду в ваш чат",
        "rp_list": "Посмотреть список рп команд",
        "rp_remove": "Удаляет существующую рп команду из вашего чата",
        "cancel": "Отменяет текущее действие",
        "privetbradok": "Поприветствовать брадка",
        "say": "Бот скажет что-то от своего имени",
        "gemini": "Бот сделает запрос к gemini",
        "aggemini": "\"Злая\" версия /gemini",
        "search": "Поиск с помощью searchgpt"
    }

    detailed_descriptions = {
        "start": "Команда-заглушка. Она нужна для проверки, работает ли бот.",
        "new_year": "Данная команда позволяет узнать, сколько времени осталось до наступления нового года.\nБот посчитает дни, часы, минуты и секунды до 1 января.",
        "birthdays": "Команда выводит информацию о днях рождения множества кошек.\nВы узнаете, через сколько дней праздновать очередной кошачий день рождения.",
        "random": "Эта команда даёт случайный ответ на ваш вопрос.\nМожет быть полезно для развлечения или принятия простых решений.",
        "help": "Команда используется для получения информации о других командах.\nПример <code>/help start<code>.",
        "rp_setup": "Устанавливает заложенные в бота рп команды в ваш чат.\n<b>ВНИМАНИЕ</b> <i>это перезапишет ваши текущие рп команды</i>.",
        "rp_add": "Добавляет новую рп команду в чат, требует прав администратора",
        "rp_list": "Просмотреть список рп команд в чате",
        "rp_remove": "Удаляет существующую рп команду из чата, требует прав администратора",
        "cancel": "Отменяет текущее действие, работает только с fsm командами, например /rp_add",
        "privetbradok": "Позволяет приветствовать своих брадков, работает по реплаям, юзернеймам и айди.\nВыдаёт рандомные приветственные фразы.\nПример: /priverbradok @komaru_dude",
        "say": "Бот скажет любую фразу от своего имени.\nПример: /say Съешь этих мягкий французских булок, да выпей чаю!",
        "gemini": "Бот сделает запрос к текстовой модели gemini-2.0-flash с использованием <a href='https://api.onlysq.ru/'>этого</a> API.\nПример: /gemini Придумай рецепт оладушков.",
        "aggemini": "Более злая версия gemini, маты, просьбы отправится куда подальше, всё это включено в эту команду, удачи.\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: /aggemini Придумай рецепт сраных оладушков",
        "search": "Бот сделает запрос в интернет с помощью поисковой модели searchgpt (gpt4-mini).\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: /search Найди рецепт оладушков."
    }

    parts = message.text.split()

    if len(parts) > 1:
        argument = parts[1].lower()
        description = detailed_descriptions.get(argument)
        if description:
            await message.reply(description, parse_mode=ParseMode.HTML)
        else:
            command_list = "\n".join(f"/{cmd} - {desc}" for cmd, desc in short_descriptions.items())
            await message.reply(
                f"Неизвестная команда.\n\n"
                f"Доступные команды:\n{command_list}\n\n"
                "Для подробного описания используйте: /help <команда>")
    else:
        command_list = "\n".join(f"/{cmd} - {desc}" for cmd, desc in short_descriptions.items())
        await message.reply(
            f"Доступные команды:\n{command_list}\n\n"
            "Для подробного описания используйте: /help <команда>")


