from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.database import DEFAULT_SETTINGS, Database
from bot.keyboards import settings_keyboard as kb_settings

settings_router = Router()


class SettingsStates(StatesGroup):
    waiting_for_input = State()


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message, db: Database):
    # Проверки прав и типа чата...
    await message.reply(
        "⚙️ <b>Главное меню настроек</b>\nВыберите категорию:",
        reply_markup=kb_settings.main_settings_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@settings_router.callback_query(F.data.startswith("category:"))
async def open_category(callback: CallbackQuery, db: Database):
    category = callback.data.split(":")[1]
    chat_id = callback.message.chat.id

    # Получаем текущие значения всех настроек в категории
    settings_state = {}
    for setting in DEFAULT_SETTINGS:
        if setting[1] == category:
            value = await db.get_setting(chat_id, setting[0])
            settings_state[setting[0]] = value if value is not None else setting[3]

    try:
        await callback.message.edit_text(
            f"⚙️ <b>Категория: {category}</b>",
            reply_markup=kb_settings.category_settings_keyboard(
                category, settings_state
            ),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass  # Игнорируем ошибку неизмененного сообщения
    await callback.answer()


@settings_router.callback_query(F.data.startswith("setting:"))
async def open_setting(callback: CallbackQuery, db: Database):
    setting_name = callback.data.split(":")[1]
    chat_id = callback.message.chat.id
    raw_value = await db.get_setting(chat_id, setting_name)

    # Получаем информацию о настройке
    setting_info = next((s for s in DEFAULT_SETTINGS if s[0] == setting_name), None)
    if not setting_info:
        await callback.answer("Настройка не найдена!")
        return

    # Преобразуем значение к правильному типу
    if setting_info[2] is bool:
        if isinstance(raw_value, str):
            current_value = raw_value.lower() == "true"
        else:
            current_value = bool(raw_value)
    else:
        current_value = raw_value

    # Если значение None, используем значение по умолчанию
    if current_value is None and len(setting_info) > 3:
        current_value = setting_info[3]

    try:
        await callback.message.edit_text(
            f"⚙️ <b>Настройка: {setting_name}</b>\nТекущее значение: {current_value}",
            reply_markup=kb_settings.setting_options_keyboard(
                setting_name, current_value
            ),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass  # Игнорируем ошибку неизмененного сообщения
    await callback.answer()


@settings_router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery):
    try:
        await callback.message.edit_text(
            "⚙️ <b>Главное меню настроек</b>\nВыберите категорию:",
            reply_markup=kb_settings.main_settings_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@settings_router.callback_query(F.data.startswith("back_to_category:"))
async def back_to_category_menu(callback: CallbackQuery, db: Database):
    category = callback.data.split(":")[1]
    chat_id = callback.message.chat.id

    settings_state = {}
    for setting in DEFAULT_SETTINGS:
        if setting[1] == category:
            value = await db.get_setting(chat_id, setting[0])
            settings_state[setting[0]] = value if value is not None else setting[3]

    try:
        await callback.message.edit_text(
            f"⚙️ <b>Категория: {category}</b>",
            reply_markup=kb_settings.category_settings_keyboard(
                category, settings_state
            ),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass
    await callback.answer()


@settings_router.callback_query(F.data.startswith("toggle_bool:"))
async def toggle_bool_setting(callback: CallbackQuery, db: Database):
    setting_name = callback.data.split(":")[1]
    chat_id = callback.message.chat.id

    # Получаем значение и гарантированно преобразуем к bool
    raw_value = await db.get_setting(chat_id, setting_name)

    # Если значение строковое, преобразуем к bool
    if isinstance(raw_value, str):
        new_value = raw_value.lower() != "true"  # Инвертируем
    else:
        new_value = not bool(raw_value)

    # Сохраняем как булево значение
    await db.set_setting(chat_id, setting_name, new_value)

    # Обновляем интерфейс
    try:
        await callback.message.edit_text(
            f"⚙️ <b>Настройка: {setting_name}</b>\nТекущее значение: {new_value}",
            reply_markup=kb_settings.setting_options_keyboard(setting_name, new_value),
            parse_mode=ParseMode.HTML,
        )
    except TelegramBadRequest:
        pass

    await callback.answer(f"Настройка изменена: {'Вкл' if new_value else 'Выкл'}")


@settings_router.callback_query(F.data.startswith("change_int:"))
async def change_int_setting(callback: CallbackQuery, db: Database):
    _, setting_name, change = callback.data.split(":")
    chat_id = callback.message.chat.id
    current_value = int(await db.get_setting(chat_id, setting_name))

    # Применяем изменение
    if change == "+1":
        new_value = current_value + 1
    elif change == "-1":
        new_value = max(0, current_value - 1)

    await db.set_setting(chat_id, setting_name, new_value)
    await open_setting(callback, db)  # Обновляем интерфейс
    await callback.answer(f"Значение изменено: {new_value}")


@settings_router.callback_query(F.data.startswith("select_option:"))
async def select_option(callback: CallbackQuery, db: Database):
    _, setting_name, option = callback.data.split(":")
    chat_id = callback.message.chat.id

    await db.set_setting(chat_id, setting_name, option)
    await open_setting(callback, db)  # Обновляем интерфейс
    await callback.answer(f"Выбрано: {option}")


# Обработчики для ввода текста
@settings_router.callback_query(F.data.startswith("input_"))
async def request_input(callback: CallbackQuery, state: FSMContext):
    input_type, setting_name = (
        callback.data.split(":")[0].split("_")[1],
        callback.data.split(":")[1],
    )

    await state.update_data(setting_name=setting_name, input_type=input_type)
    await state.set_state(SettingsStates.waiting_for_input)

    await callback.message.answer("✍️ Введите новое значение:")
    await callback.answer()


@settings_router.message(SettingsStates.waiting_for_input)
async def handle_setting_input(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    setting_name = data["setting_name"]
    input_type = data["input_type"]

    try:
        # Преобразуем в нужный тип
        if input_type == "int":
            value = int(message.text)
        elif input_type == "str":
            value = message.text
        else:
            value = message.text  # По умолчанию строка
    except ValueError:
        await message.reply("❌ Некорректный формат. Попробуйте снова.")
        return

    # Сохраняем значение
    await db.set_setting(message.chat.id, setting_name, value)
    await message.reply(f"✅ Значение для {setting_name} успешно обновлено!")
    await state.clear()


@settings_router.message(Command("restore_default_settings"))
async def cmd_restore_settings(message: Message, db: Database):
    user_id = message.from_user.id
    if not await db.has_permission(user_id, message.chat.id, 3):
        await message.reply(
            "❌ Право сбрасывать настройки имеет только владелец чата или персонал бота"
        )
        return

    await message.reply(
        "❓ Вы уверены?\n\n♨️ Это действие необратимо",
        reply_markup=kb_settings.restore_settings_keyboard(user_id),
    )


@settings_router.callback_query(F.data.startswith("restore_default_settings:"))
async def callback_restore_settings(callback: CallbackQuery, db: Database):
    parts = callback.data.split(":")
    answer = parts[1]
    callback_user_id = parts[2]

    if callback.from_user.id != int(callback_user_id):
        await callback.answer(
            "❌ Комару не разрешает отвечать на чужие колбэки", show_alert=True
        )
        return

    if answer == "no":
        await callback.answer("⛔️ Отменено")
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            await callback.answer("📛 У меня не получилось удалить своё сообщение")
    else:
        await db.restore_chat_settings(callback.message.chat.id)
        try:
            await callback.message.delete()
        except TelegramBadRequest:
            await callback.answer("📛 У меня не получилось удалить своё сообщение")
        await callback.answer("✅ Успешно сброшено")
