import traceback
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot.utils.aio_tools import error_report

help_router = Router()


@help_router.message(Command("help"))
async def cmd_help(message: Message, bot: Bot):
    try:
        cmd_short_descriptions = {
            "start": "Базовая команда, выступает заглушкой",
            "status": "Информация о времени работы бота",
            "update": "Обновляет бота",
            "restart": "Перезапускает бота",
            "help": "Помощь по командам",
            "cancel": "Отменяет текущее действие",
            "new_year": "Время до нового года",
            "birthdays": "Время до дня рождения кошек",
            "random": "Рандомный ответ на ваш вопрос",
            "weather": "Прогноз погоды",
            "privetbradok": "Поприветствовать брадка",
            "http_cat": "Рандомный кот с http.cat",
            "http_dog": "Рандомная собака с http.dog",
            "cat": "Отправляет рандомную фотку кота",
            "cat_gif": "Отправляет рандомную гифку с котом",
            "shutter": "Преобразует текст в залипания",
            "gemini": "Бот сделает запрос к gemini",
            "aggemini": '"Злая" версия /gemini',
            "deepseek": "Бот сделает запрос к deepseek-r1",
            "agdeepseek": '"Злая" версия /deepseek',
            "arguechat": "Начать спор с ИИ",
            "image": "Бот сделает запрос к Kandinsky",
            "search": "Поиск с помощью searchgpt",
            "vocr": "Распознать текст с картинки",
            "translate": "Бот переведёт текст",
            "say": "Бот скажет что-то от своего имени",
            "rp_setup": "Первично настроивает рп команды в вашем чате",
            "rp_add": "Добавляет новую рп команду в ваш чат",
            "rp_list": "Посмотреть список рп команд",
            "rp_remove": "Удаляет существующую рп команду из вашего чата",
            "video": "Скачать видео",
            "gif": "Конвертирует видео в гифку (не используется)",
            "jpeg": "Шакализирует картинку",
            "set_rank": "Устанавливает ранг",
            "enable": "Включить функцию в чате",
            "disable": "Выключить функцию в чате",
        }

        cmd_detailed_descriptions = {
            "start": "Команда-заглушка. Она нужна для проверки, работает ли бот.",
            "status": "Выводит некоторую информацию о времени работы и загруженности бота.",
            "update": "Обновляет бота до последней доступной на github версии.\n\n📛 <b>Только</b> для персонала",
            "restart": " Перезапускает бота (и вместе с этим обновляет)\n\n📛 <b>Только</b> для персонала",
            "help": "Команда используется для получения информации о других командах.\nПример <code>/help start</code>.",
            "cancel": "Отменяет текущее действие, работает только с fsm командами, например <code>/rp_add</code>",
            "new_year": "Данная команда позволяет узнать, сколько времени осталось до наступления нового года.\nБот посчитает дни, часы, минуты и секунды до 1 января.",
            "birthdays": "Команда выводит информацию о днях рождения множества кошек.\nВы узнаете, через сколько дней праздновать очередной кошачий день рождения.",
            "random": "Эта команда даёт случайный ответ на ваш вопрос.\nМожет быть полезно для развлечения или принятия простых решений.",
            "weather": "Позволяет узнать погоду, в качестве аргумента принимает имя города.\nПример: <code>/weather Москва</code>",
            "privetbradok": "Позволяет приветствовать своих брадков, работает по реплаям, юзернеймам и айди.\nВыдаёт рандомные приветственные фразы.\nПример: <code>/privetbradok @username</code>",
            "http_cat": "Отправляет в ответ рандомного кота с http.cat.\nПоддерживается ручной ввод http кода.\nПример: <code>/http_cat 100</code>",
            "http_dog": "Отправляет в ответ рандомную собаку с http.dog.\nПоддерживается ручной ввод http кода.\nПример: <code>/http_dog 200</code>",
            "cat": "Отправляет фотку рандомного кота через <a href='https://catass.com'>этот</a> сервис",
            "cat_gif": "Отправляет гифку рандомного кота через <a href='https://catass.com'>этот</a> сервис",
            "shutter": 'Преобразует текст в запинания в стиле "п-по-пожалуйста~~🥺".\nРаботает как по тексту, так и по реплаям.\nПример: <code>/shutter Привет</code>',
            "gemini": "Бот сделает запрос к текстовой модели gemini-2.0-flash с использованием <a href='https://api.onlysq.ru/'>этого</a> API.\nПример: <code>/gemini Придумай рецепт оладушков.</code>",
            "aggemini": "Более злая версия /gemini, маты, просьбы отправится куда подальше, всё это включено в эту команду.\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: <code>/aggemini Привет, я умный</code>",
            "deepseek": "Бот сделает запрос к текстовой модели deepseek-r1 с использованием <a href='https://api.onlysq.ru/'>этого</a> API.\n⚠️ Ответы могут быть долгими (>25 секунд)\nПример: <code>/deepseek Придумай рецепт оладушков.</code>",
            "agdeepseek": "Более злая версия /deepseek, маты, просьбы отправится куда подальше, всё это включено в эту команду.\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: <code>/agdeepseek Привет, я умный</code>",
            "arguechat": "Начинает спор с gpt-4o-mini.\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\n\nОстановить спор можно через <code>/cancel</code>",
            "image": "Простой генератор картинок на основе Kandinsky.\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: <code>/image кошечка плап</code>",
            "search": "Бот сделает запрос в интернет с помощью поисковой модели searchgpt (gpt4-mini).\nИспользуется <a href='https://api.onlysq.ru/'>этот</a> API.\nПример: <code>/search Найди рецепт оладушек</code>",
            "vocr": "Бот с помощью jigsaw ai распознает текст на картинке, работает через прикреплённую картинку/реплай.",
            "translate": "Простой переводчик на основе jigsaw ai.\nПример: <code>/translate en Привет брадок, как дела?</code>\n\n⚠️ Для перевода единичных слов лучше использовать <code>/gemini</code>",
            "say": "Бот скажет любую фразу от своего имени.\nПример: <code>/say Текст сообщения</code>",
            "rp_setup": "Устанавливает заложенные в бота рп команды в ваш чат.\n<b>ВНИМАНИЕ</b> <i>это перезапишет ваши текущие рп команды</i>.",
            "rp_add": "Добавляет новую рп команду в чат, требует прав администратора",
            "rp_list": "Просмотреть список рп команд в чате",
            "rp_remove": "Удаляет существующую рп команду из чата, требует прав администратора\nПример: <code>/rp_remove тостер</code>",
            "video": "Скачивает видео с <a href='https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md'>этих</a> сайтов.\n⚠️ Могут быть проблемы с сайтами заблокированными в РФ\nПример: <code>/video https://www.youtube.com/watch?v=dQw4w9WgXcQ</code>",
            "gif": "Конвертирует видео в гифку\nРаботает по реплаям/прикреплённым гифкам",
            "jpeg": "Крайне сильно шакализирует гифку с использованием ffmpeg\nРаботает по реплаям/прикреплённым изображениям",
            "set_rank": "Используется для установки ранга пользователю, ранги нужны для управления доступами к командам.\nДоступ только для ВЛАДЕЛЬЦА чата или Администратора.",
            "enable": "Включает функцию, требует права модератора.\nПример: <code>/enable who</code>",
            "disable": "Выключает функцию, требует права модератора.\nПример: <code>/disable who</code>",
        }

        mod_short_descriptions = {
            "who": 'Написали "это что?" — бот спросит нейросеть и ответит.',
            "tag": "Даёт доступ обычным людям упоминать через /tag и /tagall",
            "autovideo": "Автоматическая загрузка видео",
            "warn": "Позволяет предупреждать пользователей",
            "mute": "Позволяет мьютить пользователей",
            "ban": "Позволяет банить пользователей",
        }

        mod_detailed_descriptions = {
            "who": '💬 Если кто-то ответит на сообщение словами "это что?", бот спросит у нейросети (gpt-4o-mini), что это такое.\n\n⚠️ Работает только с текстом',
            "tag": "❇️ При включении функции <b>ЛЮБОЙ</b> человек сможет упоминать других через /tag и /tagall.\n📌 По умолчанию доступ только для модераторов.",
            "autovideo": "🔄 Автоматически загружает видео отправленные в чат.\nРаботают не все сайты из /video.",
            "warn": "📝 Модуль добавляет команду /warn для выдачи предупреждений.",
            "mute": "🔇 Позволяет временно отключать возможность отправки сообщений через /mute.",
            "ban": "📛 Разрешает команду /ban для блокировки пользователей.",
        }

        parts = message.text.split()

        if len(parts) > 1:
            argument = parts[1].lower()
            cmd_description = cmd_detailed_descriptions.get(argument)
            mod_description = mod_detailed_descriptions.get(argument)
            if cmd_description:
                await message.reply(
                    cmd_description,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            elif mod_description:
                await message.reply(
                    mod_description,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            else:
                command_list = "\n".join(
                    f"/{cmd} - {desc}" for cmd, desc in cmd_short_descriptions.items()
                )
                modules_list = "\n".join(
                    f"{mod} - {desc}" for mod, desc in mod_short_descriptions.items()
                )
                await message.reply(
                    f"Неизвестная команда или модуль.\n\n"
                    f"Доступные команды:\n{command_list}\n\n"
                    f"Доступные модули:\n{modules_list}\n\n"
                    "Для подробного описания используйте: /help <команда или модуль>\n"
                    "Пример: /help image"
                )
        else:
            command_list = "\n".join(
                f"/{cmd} - {desc}" for cmd, desc in cmd_short_descriptions.items()
            )
            modules_list = "\n".join(
                f"{mod} - {desc}" for mod, desc in mod_short_descriptions.items()
            )
            await message.reply(
                f"Доступные команды:\n{command_list}\n\n"
                f"Доступные модули:\n{modules_list}\n\n"
                "Для подробного описания используйте: /help <команда или модуль>"
            )
    except Exception:
        await error_report(message, bot, "help", traceback.format_exc())
