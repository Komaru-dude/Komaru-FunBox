from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

help_router = Router()

@help_router.message(Command("help"))
async def cmd_help(message: Message):
    cmd_short_descriptions = {
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
        "image": "Бот сделает запрос к Kandinsky",
        "search": "Поиск с помощью searchgpt",
        "set_rank": "Устанавливает ранг",
        "enable": "Включить функцию в чате",
        "disable": "Выключить функцию в чате",
        "shutter": "Преобразует текст в залипания"
    }

    cmd_detailed_descriptions = {
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
        "image": "Простой генератор картинок на основе Kandinsky\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: /image кошечка плап\n\nP.S. Если модель выдаёт вам цветочные поля и подобные заполнители значит пора начать писать нормальные промпты.",
        "search": "Бот сделает запрос в интернет с помощью поисковой модели searchgpt (gpt4-mini).\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: /search Найди рецепт оладушков.",
        "set_rank": "Используется для установки ранга пользователю, ранги нужны для управления доступами к командам.\nДоступ к этой команда имеет только <b>ВЛАДЕЛЕЦ</b> чата или его администратор.",
        "enable": "Включает функцию, требует права модератора для использования.\nПример: /enable who - включает функцию \"это что?\"",
        "disable": "Выключает функцию, требует права модератора для использования.\nПример: /disable who - выключает функцию \"это что?\"",
        "shutter": "Преобразует текст в запинания в стиле \"п-по-пожалуйста~~🥺\".\nРаботает как по тексту, так и по реплаям"
    }

    mod_short_descriptions ={
        "who": "Написали \"это что?\" — бот спросит нейросеть и ответит.",
        "tag": "Даёт доступ обычным людям упоминать через /tag и /tagall"
    }

    mod_detailed_descriptions = {
        "who": "💬 Если кто-то ответит на сообщение словами \"это что?\", бот спросит у нейросети (gemini-2.0-flash), что это такое, и пришлёт ответ.\n\n⚠️ Работает только с текстом",
        "tag": "❇️ При включении функции <b>ЛЮБОЙ</b> человек сможет упоминать других через /tag и /tagall.\n📌 По умолчанию доступ к этим командам имеют только модераторы и выше.\n\nПоддерживает текст в конце."
    }

    parts = message.text.split()

    if len(parts) > 1:
        argument = parts[1].lower()
        cmd_description = cmd_detailed_descriptions.get(argument)
        mod_description = mod_detailed_descriptions.get(argument)
        if cmd_description:
            await message.reply(cmd_description, parse_mode=ParseMode.HTML)
        elif mod_description:
            await message.reply(mod_description, parse_mode=ParseMode.HTML)
        else:
            command_list = "\n".join(f"/{cmd} - {desc}" for cmd, desc in cmd_short_descriptions.items())
            modules_list = "\n".join(f"{mod} - {desc}" for mod, desc in mod_short_descriptions.items())  
            await message.reply(
                f"Неизвестная команда или модуль.\n\n"
                f"Доступные команды:\n{command_list}\n\n"
                f"Доступные модули:\n{modules_list}\n\n"
                "Для подробного описания используйте: /help <команда или модуль>\n"
                "Пример: /help image")
    else:
        command_list = "\n".join(f"/{cmd} - {desc}" for cmd, desc in cmd_short_descriptions.items())
        modules_list = "\n".join(f"{mod} - {desc}" for mod, desc in mod_short_descriptions.items())  
        await message.reply(
            f"Доступные команды:\n{command_list}\n\n"
            f"Доступные модули:\n{modules_list}\n\n"
            "Для подробного описания используйте: /help <команда или модуль>")


