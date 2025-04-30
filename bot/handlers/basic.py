import random
import os
import time
import psutil
import traceback
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from bot import db
from bot.utils.aio_tools import fetch_json, error_report, get_user_id, fetch_user_data

base_router = Router()
current_dir = os.path.dirname(os.path.abspath(__file__))
media_folder = os.path.join(current_dir, "..", "media")
sticker_extensions = {".webp", ".tgs", ".webm"}
API_URL = "http://127.0.0.1:8001"
# Списки хранения данных для /status
cpu_loads = []
memory_loads = []
start_time = time.time()


@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "Привет!\n"
        "Это развлекательный и модерационный бот бот.\n"
        "Если хочешь узнать более подробную информацию о командах: /help"
    )


@base_router.message(Command("status"))
async def cmd_status(message: Message, bot: Bot):
    try:
        global start_time

        ping_start_time = time.monotonic()
        sent_message = await message.reply("⏳")
        end_time = time.monotonic()
        ping = (end_time - ping_start_time) * 1000  # В миллисекундах
        current_time = time.time()
        uptime_seconds = int(current_time - start_time)

        # Получаем текущую загрузку процессора и памяти
        cpu_percent = psutil.cpu_percent(interval=1)
        memory_percent = psutil.virtual_memory().percent

        # Добавляем данные в списки с отметкой времени
        cpu_loads.append((current_time, cpu_percent))
        memory_loads.append((current_time, memory_percent))

        # Убираем данные старше 5 минут
        five_minutes_ago = current_time - 300
        cpu_loads[:] = [(t, load) for t, load in cpu_loads if t >= five_minutes_ago]
        memory_loads[:] = [
            (t, load) for t, load in memory_loads if t >= five_minutes_ago
        ]

        # Вычисляем среднее значение за последние 5 минут
        avg_cpu_load = (
            sum(load for _, load in cpu_loads) / len(cpu_loads) if cpu_loads else 0
        )
        avg_memory_load = (
            sum(load for _, load in memory_loads) / len(memory_loads)
            if memory_loads
            else 0
        )

        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60

        uptime_str = f"{days}д {hours}ч {minutes}м {seconds}с"
        await sent_message.edit_text(
            f"⏳ Пинг: {int(ping)} мс\n"
            f"🚀 Бот работает: {uptime_str}\n"
            f"📊 Средняя загруженность ЦПУ (5м): {avg_cpu_load:.2f}%\n"
            f"📊 Средняя загруженность ОЗУ (5м): {avg_memory_load:.2f}%"
        )
    except Exception:
        await error_report(message, bot, "status", traceback.format_exc())


@base_router.message(Command("random"))
async def cmd_random(message: Message, bot: Bot):
    try:
        responses = [
            "Да, без сомнений!",
            "Нет, это не сбудется.",
            "Возможно, ты прав.",
            "Скорее всего, да.",
            "Попробуй снова позже.",
            "Определенно нет.",
            "Я бы сказал да.",
        ]
        response = random.choice(responses)
        await message.reply(response)
    except Exception:
        await error_report(message, bot, "random", traceback.format_exc())


@base_router.message(Command("cancel"))
async def cmd_cancel(message: Message, bot: Bot, state: FSMContext):
    try:
        current_state = await state.get_state()
        if current_state is None:
            await message.reply("📛 Нечего отменять")
        else:
            await state.clear()
            await message.reply("❌ Отменено")
    except Exception:
        await error_report(message, bot, "cancel", traceback.format_exc())


@base_router.message(Command("privetbradok"))
async def cmd_privebradok(message: Message, bot: Bot):
    try:
        target_id = None
        first_name = None

        if message.reply_to_message:
            target_id = message.reply_to_message.from_user.id
            first_name = message.reply_to_message.from_user.first_name
        else:
            text = message.text
            split_text = text.split(maxsplit=1)

            if len(split_text) > 1 and split_text[1].startswith("@"):
                username = split_text[1][1:]
                try:
                    data = await fetch_json(f"{API_URL}/user/{username}")

                    if "user_id" in data:
                        target_id = data["user_id"]
                        name_data = await fetch_json(
                            f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                        )
                        first_name = name_data.get("first_name", "Неизвестный")
                    else:
                        await message.reply(
                            f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}"
                        )
                        return

                except Exception as e:
                    await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                    return
            elif len(split_text) > 1 and split_text[1].isdigit():
                target_id = split_text[1]
                try:
                    data = await fetch_json(
                        f"{API_URL}/first_name/{message.chat.id}/{target_id}"
                    )
                    first_name = data.get("first_name", "Неизвестный")
                except Exception as e:
                    await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                    return
            else:
                await message.reply(
                    "Укажите пользователя через реплай, @username или айди."
                )
                return

        user2_link = f'<a href="tg://user?id={target_id}">{first_name}</a>'

        stick = random.choice([True, False])

        if message.reply_to_message and not stick:
            await message.reply_to_message.reply(
                f"Привет {user2_link}!", parse_mode=ParseMode.HTML
            )
        elif not stick:
            await message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
        else:
            stickers = [
                f
                for f in os.listdir(media_folder)
                if os.path.splitext(f)[1].lower() in sticker_extensions
            ]
            if not stickers:
                raise FileNotFoundError("Нет стикеров в ../media")
            random_stick = random.choice(stickers)
            sticker = FSInputFile(os.path.join(media_folder, random_stick))
            if message.reply_to_message:
                await message.reply_to_message.reply_sticker(sticker)
            else:
                await message.reply_sticker(sticker)
    except Exception:
        await error_report(message, bot, "privetbradok", traceback.format_exc())


@base_router.message(Command("say"))
async def cmd_say(message: Message, bot: Bot):
    try:
        split_text = message.text.split(maxsplit=1)
        if len(split_text) > 1:
            await message.answer(split_text[1])
            try:
                await message.delete()
            except:
                await message.answer(
                    "Брадочки, оформите права на удаление сообщений 😢"
                )
        else:
            await message.reply("А что говорить то?")
    except Exception:
        await error_report(message, bot, "say", traceback.format_exc())


@base_router.message(Command("shutter"))
async def cmd_shutter(message: Message, bot: Bot):
    try:

        def generate_stutter(word):
            if len(word) < 2 or not word[0].isalpha():
                return word

            stutter_type = random.choice(
                [
                    "repeat",
                    "repeat",
                    "hyphenated",
                    "double_hyphen",
                    "ellipsis",
                    "spacey",
                    "mixed_case",
                ]
            )

            repeats = random.randint(1, 3)
            first_letter = (
                word[0].upper() if random.choice([True, False]) else word[0].lower()
            )
            second_letter = (
                word[1].lower() if random.choice([True, False]) else word[1].upper()
            )

            if random.random() < 0.3:
                interjections = ["м-м", "э-э", "х-х", "а-а", "з-з"]
                word = f"{random.choice(interjections)}... {word}"

            if stutter_type == "repeat":
                parts = [f"{first_letter}-" * repeats + word]
            elif stutter_type == "hyphenated":
                parts = [f"{first_letter}-{second_letter}-{word}"]
            elif stutter_type == "double_hyphen":
                parts = [f"{first_letter}--{second_letter}--{word}"]
            elif stutter_type == "ellipsis":
                parts = [f"{first_letter}...{second_letter}...{word}"]
            elif stutter_type == "spacey":
                parts = [f"{first_letter} {second_letter} {word}"]
            elif stutter_type == "mixed_case":
                parts = [f"{first_letter.lower()}-{second_letter.upper()}-{word}"]

            if random.random() < 0.2:
                parts.append("...")

            return "".join(parts)

        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
        else:
            parts = message.text.split(maxsplit=1)
            if len(parts) < 2:
                await message.reply("❌ А что конвертировать?")
                return
            text = parts[1]

        words = text.split()
        result = []

        emojis = ["😅", "🤔", "🙄", "😬", "😶", "🤷"]

        for word in words:
            if random.random() < 0.4:
                stuttered = generate_stutter(word)

                if random.random() < 0.4:
                    stuttered = stuttered.replace(" ", f" {random.choice(emojis)} ", 1)

                result.append(stuttered)
            else:
                result.append(word)

            if random.random() < 0.2:
                result.append(random.choice(emojis))

        final_text = " ".join(result)

        suffixes = [
            f"~~ {random.choice(emojis)}",
            f"/// {random.choice(emojis)}",
            f"☆*:.｡.o(≧▽≦)o.｡.:*☆",
            f"{random.choice(['~', '*', ''])} {random.choice(emojis)} {random.choice(emojis)}",
            "(｡♥‿♥｡)",
            "(≧◡≦) ♡",
            "(｡•́‿•̀｡)ฅ",
            "(^•ﻌ•^) ฅ",
            "(๑>◡<๑)",
            "(づ｡◕‿‿◕｡)づ",
            "(*≧ω≦)",
            "(ღ✪v✪)｡o♡",
            "(U ᵕ U❁)",
            "(๑˃ᴗ˂)ﻭ",
            "(*°▽°*)",
            "(✿◠‿◠)",
            "(ฅ^•ﻌ•^ฅ)",
            "♡＾▽＾♡",
            "(๑ᴖ◡ᴖ๑)",
            "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
            "(ʘ‿ʘ)✿",
            "(◕‿◕✿)",
            "(✧ω✧)",
            "(๑´• .̫ • `๑)",
            "(っ˘ω˘ς )",
            "(*ฅ́˘ฅ̀*)♡",
            "(つ≧▽≦)つ",
            "(◍•ᴗ•◍)♡",
            "✧(＾◡＾)✿",
        ]

        if random.random() < 0.2:
            prefixes = ["А-а... ", "Э-э... ", "М-м... ", "Ну..."]
            final_text = random.choice(prefixes) + final_text

        final_text += f" {random.choice(suffixes)}"

        if random.random() < 0.25:
            final_text += random.choice(["...", "..~~", "……"])

        if len(final_text) > 4096:
            chunks = [final_text[i : i + 4096] for i in range(0, len(final_text), 4096)]
        else:
            chunks = [final_text]
        for idx, chunk in enumerate(chunks):
            if idx == 0:
                await message.reply(chunk)
            else:
                await message.answer(chunk)
    except Exception:
        await error_report(message, bot, "shutter", traceback.format_exc())


@base_router.message(Command("info"))
async def cmd_info(message: Message, bot: Bot):
    try:
        chat_id = message.chat.id
        split_text = message.text.split()
        error = None
        if len(split_text) < 2:
            user_id = message.from_user.id
        else:
            user_id, error = await get_user_id(message)

        if error:
            return await message.reply(f"❌ {error}")

        user_info = await fetch_user_data(user_id=user_id, chat_id=chat_id)
        if "error" in user_info:
            return await message.reply(f"❌ {user_info['error']}")

        user_data = db.get_user_data(user_info["user_id"], chat_id)
        if not user_data:
            return await message.reply("❌ Пользователь не найден в базе данных")

        profile_link = f"tg://user?id={user_info['user_id']}"
        clickable_name = f'<a href="{profile_link}">{user_info["first_name"]}</a>'

        info_text = (
            f"👤 Информация о {clickable_name}\n"
            f"🆔 ID: {user_info['user_id']}\n"
            f"📊 Статистика:\n"
            f"⚠ Предупреждения: {user_data[2]}/{user_data[9]}\n"
            f"🔇 Мьюты: {user_data[4]}\n"
            f"🔨 Баны: {user_data[3]}\n"
            f"💎 Репутация: {user_data[5]}\n"
            f"📨 Сообщений: {user_data[7]}\n"
            f"🏅 Ранг: {user_data[6]}\n"
        )

        await message.reply(info_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await error_report(message, bot, "info", traceback.format_exc())
