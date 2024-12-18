from aiogram import Router
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import db

rp_router = Router()

@rp_router.message()
async def text(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Проверяем, если пользователь ещё не добавлен в базу данных, добавляем его
    if not db.user_exists(user_id):
        db.add_user(user_id)
    if not db.user_have_username(user_id):
        db.add_username(user_id, username=username)
    if not db.user_have_first_name(user_id):
        db.add_first_name(user_id, first_name)

    if message.text and 'сжечь' in message.text.lower():
        parts = message.text.split()
        
        if len(parts) > 1:
            target_username = parts[1].lstrip('@')
            if not db.get_user_id_by_username(target_username):
                await message.reply("Синтаксис некорректен, используйте 'сжечь @пользователь' или ответьте на сообщение пользователя")
                return
            else:
                target_id = db.get_user_id_by_username(target_username)
                target_first_name = db.get_first_name_by_id(target_id)
                
                # Создаём ссылку на профили обоих пользователей
                profile_link = f"tg://user?id={user_id}"
                clickable_name_user1 = f"<a href='{profile_link}'>{first_name}</a>"

                target_profile_link = f"tg://user?id={target_id}"
                clickable_name_user2 = f"<a href='{target_profile_link}'>{target_first_name}</a>"
                
                # Формируем сообщение с эмодзи и ссылками
                await message.answer(f"🔥 {clickable_name_user1} сжёг {clickable_name_user2}", parse_mode=ParseMode.HTML)
