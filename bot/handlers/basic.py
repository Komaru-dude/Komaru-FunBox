import random, aiohttp, os, time, psutil
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

base_router = Router()
current_dir = os.path.dirname(os.path.abspath(__file__))
media_folder = os.path.join(current_dir, '..', 'media')
sticker_extensions = {".webp", ".tgs", ".webm"}
API_URL = "http://127.0.0.1:8001"
# Списки хранения данных для /status
cpu_loads = []
memory_loads = []
start_time = time.time()

async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка API: статус {response.status}")
            return await response.json()

@base_router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("Привет!\n"
                        "Это развлекательный и модерационный бот бот.\n"
                        "Если хочешь узнать более подробную информацию о командах: /help")
    
@base_router.message(Command("status"))
async def cmd_status(message: Message):
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
    memory_loads[:] = [(t, load) for t, load in memory_loads if t >= five_minutes_ago]

    # Вычисляем среднее значение за последние 5 минут
    avg_cpu_load = sum(load for _, load in cpu_loads) / len(cpu_loads) if cpu_loads else 0
    avg_memory_load = sum(load for _, load in memory_loads) / len(memory_loads) if memory_loads else 0

    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60

    uptime_str = f"{days}д {hours}ч {minutes}м {seconds}с"
    await sent_message.edit_text(f"⏳ Пинг: {int(ping)} мс\n"
                                 f"🚀 Бот работает: {uptime_str}\n"
                                 f"📊 Средняя загруженность ЦПУ (5м): {avg_cpu_load:.2f}%\n"
                                 f"📊 Средняя загруженность ОЗУ (5м): {avg_memory_load:.2f}%")
    
@base_router.message(Command("random"))
async def cmd_random(message: Message):
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

@base_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.reply("А чего отменять то?")
    else:
        await state.clear()
        await message.reply("❌ Отменено")

@base_router.message(Command('privetbradok'))
async def cmd_privebradok(message: Message):
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
                    name_data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                    first_name = name_data.get("first_name", "Неизвестный")
                else:
                    await message.reply(f"Не удалось найти пользователя: {data.get('error', 'Неизвестная ошибка')}")
                    return

            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        elif len(split_text) > 1 and split_text[1].isdigit():
            target_id = split_text[1]
            try:
                data = await fetch_json(f"{API_URL}/first_name/{message.chat.id}/{target_id}")
                first_name = data.get("first_name", "Неизвестный")
            except Exception as e:
                await message.reply(f"Произошла ошибка {e} при обработке запроса.")
                return
        else:
            await message.reply("Укажите пользователя через реплай, @username или айди.")
            return

    user2_link = f'<a href="tg://user?id={target_id}">{first_name}</a>'

    stick = random.choice([True, False])

    if message.reply_to_message and not stick:
         await message.reply_to_message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
    elif not stick:
        await message.reply(f"Привет {user2_link}!", parse_mode=ParseMode.HTML)
    else:
        stickers = [f for f in os.listdir(media_folder) if os.path.splitext(f)[1].lower() in sticker_extensions]
        if not stickers:
            raise FileNotFoundError("Нет стикеров в ../media")
        random_stick = random.choice(stickers)
        sticker = FSInputFile(os.path.join(media_folder, random_stick))
        if message.reply_to_message:
            await message.reply_to_message.reply_sticker(sticker)
        else:
            await message.reply_sticker(sticker)

@base_router.message(Command("say"))
async def cmd_say(message: Message):
    split_text = message.text.split(maxsplit=1)
    if len(split_text) > 1:
        await message.answer(split_text[1])
        try:
            await message.delete()
        except:
            await message.answer("Брадочки, оформите права на удаление сообщений 😢")
    else:
        await message.reply("А что говорить то?")

@base_router.message(Command("shutter"))
async def cmd_shutter(message: Message):
    def generate_stutter(word):
        if len(word) < 2 or not word[0].isalpha():
            return word
        
        # Разные варианты шаттера
        stutter_type = random.choice([
            'repeat', 
            'repeat',  # Повторяем дважды для большей вероятности
            'hyphenated',
            'double_hyphen',
            'ellipsis',
            'spacey',
            'mixed_case'
        ])
        
        # Случайное количество повторов (1-3)
        repeats = random.randint(1, 3)
        first_letter = word[0].upper() if random.choice([True, False]) else word[0].lower()
        second_letter = word[1].lower() if random.choice([True, False]) else word[1].upper()
        
        # Добавляем междометия
        if random.random() < 0.3:
            interjections = ['м-м', 'э-э', 'х-х', 'а-а', 'з-з']
            word = f"{random.choice(interjections)}... {word}"

        # Генерация разных типов шаттера
        if stutter_type == 'repeat':
            parts = [f"{first_letter}-" * repeats + word]
        elif stutter_type == 'hyphenated':
            parts = [f"{first_letter}-{second_letter}-{word}"]
        elif stutter_type == 'double_hyphen':
            parts = [f"{first_letter}--{second_letter}--{word}"]
        elif stutter_type == 'ellipsis':
            parts = [f"{first_letter}...{second_letter}...{word}"]
        elif stutter_type == 'spacey':
            parts = [f"{first_letter} {second_letter} {word}"]
        elif stutter_type == 'mixed_case':
            parts = [f"{first_letter.lower()}-{second_letter.upper()}-{word}"]
        
        # Случайное обрезание слова
        if random.random() < 0.2:
            parts.append('...')
        
        return ''.join(parts)
    
    # Получение текста
    if message.reply_to_message:
        text = message.reply_to_message.text
    else:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("❌ А что конвертировать?")
            return
        text = parts[1]

    words = text.split()
    result = []

    emojis = [
        '😳', '😣', '🥵', '😰', '😥', '😓', '😖', '😵', '💦', 
        '🌊', '💫', '✨', '🌸', '🫠', '🤤', '🙀', '🎀', '💔'
    ]
    
    for word in words:
        if random.random() < 0.8:
            stuttered = generate_stutter(word)
            
            # Добавление эмодзи внутри слов
            if random.random() < 0.4:
                stuttered = stuttered.replace(' ', f" {random.choice(emojis)} ", 1)
                
            result.append(stuttered)
        else:
            result.append(word)
        
        # Добавление случайных эмодзи после слов
        if random.random() < 0.3:
            result.append(random.choice(emojis))
    
    # Финал с дополнительными эффектами
    final_text = ' '.join(result)
    
    # Добавляем суффиксы с эмодзи
    suffixes = [
        f"~~ {random.choice(emojis)}",
        f"/// {random.choice(emojis)}",
        f"☆*:.｡.o(≧▽≦)o.｡.:*☆",
        f"{random.choice(['~', '*', ''])} {random.choice(emojis)} {random.choice(emojis)}"
    ]
    
    # Случайный префикс
    if random.random() < 0.15:
        prefixes = ["А-а... ", "Э-э... ", "М-м... ", "✨ ", "💫 "]
        final_text = random.choice(prefixes) + final_text
    
    final_text += f" {random.choice(suffixes)}"
    
    # Случайные многоточия в конце
    if random.random() < 0.25:
        final_text += random.choice(["...", "..~~", "……"])
    
    await message.reply(final_text)