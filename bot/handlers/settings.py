from traceback import format_exc

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.database import DEFAULT_SETTINGS, Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.keyboards import settings_keyboard as kb_settings
from bot.utils.aio_tools import error_report

settings_router = Router()


class SettingsStates(StatesGroup):
    waiting_for_input = State()


@settings_router.message(
    Command("settings"),
    CooldownFilter("settings", 15),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
)
async def cmd_settings(message: Message, bot: Bot, db: Database):
    user_id = message.from_user.id
    try:
        if not await db.has_permission(user_id, message.chat.id, 2):
            await message.reply(
                "❌ Редактировать настройки могут только модераторы и выше"
            )
            return

        await message.reply(
            "⚙️ <b>Главное меню настроек</b>\nВыберите категорию:",
            reply_markup=kb_settings.main_settings_keyboard(owner_id=user_id),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("category:"))
async def open_category(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "category:<category>:<owner_id>"
    _, category, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id

        # Получаем текущие значения всех настроек в категории
        settings_state = {}
        for setting in DEFAULT_SETTINGS:
            if setting[1] == category:
                value = await db.get_setting(chat_id, setting[0])
                settings_state[setting[0]] = value if value is not None else setting[3]

        await callback.message.edit_text(
            f"⚙️ <b>Категория: {category}</b>",
            reply_markup=kb_settings.category_settings_keyboard(
                category, settings_state, owner_id=owner_id
            ),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
    except TelegramBadRequest:
        pass
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("setting:"))
async def open_setting(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "setting:<name>:<owner_id>"
    _, setting_name, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id
        raw_value = await db.get_setting(chat_id, setting_name)

        # Инфо о настройке
        setting_info = next((s for s in DEFAULT_SETTINGS if s[0] == setting_name), None)
        if not setting_info:
            await callback.answer("Настройка не найдена!")
            return

        # Преобразуем к bool
        if setting_info[2] is bool:
            if isinstance(raw_value, str):
                current_value = raw_value.lower() == "true"
            else:
                current_value = bool(raw_value)
        else:
            current_value = raw_value

        if current_value is None and len(setting_info) > 3:
            current_value = setting_info[3]

        await callback.message.edit_text(
            f"⚙️ <b>Настройка: {setting_name}</b>\n"
            f"📒 <b>Описание:</b> {setting_info[4]}\n"
            f"🔢 Текущее значение: {current_value}",
            reply_markup=kb_settings.setting_options_keyboard(
                setting_name, current_value, owner_id=owner_id
            ),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
    except TelegramBadRequest:
        pass
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("close_settings"))
async def close_settings(callback: CallbackQuery, bot: Bot):
    # callback.data = "close_settings:<owner_id>"
    data = callback.data.split(":")
    owner_id = int(data[1]) if len(data) > 1 else None

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass
    await callback.answer()


@settings_router.callback_query(F.data.startswith("back_to_main:"))
async def back_to_main_menu(callback: CallbackQuery, bot: Bot):
    # callback.data = "back_to_main:<owner_id>"
    _, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        await callback.message.edit_text(
            "⚙️ <b>Главное меню настроек</b>\nВыберите категорию:",
            reply_markup=kb_settings.main_settings_keyboard(owner_id=owner_id),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
    except TelegramBadRequest:
        pass
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("back_to_category:"))
async def back_to_category_menu(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "back_to_category:<category>:<owner_id>"
    _, category, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id
        settings_state = {}
        for setting in DEFAULT_SETTINGS:
            if setting[1] == category:
                value = await db.get_setting(chat_id, setting[0])
                settings_state[setting[0]] = value if value is not None else setting[3]

        await callback.message.edit_text(
            f"⚙️ <b>Категория: {category}</b>",
            reply_markup=kb_settings.category_settings_keyboard(
                category, settings_state, owner_id=owner_id
            ),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
    except TelegramBadRequest:
        pass
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("toggle_bool:"))
async def toggle_bool_setting(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "toggle_bool:<name>:<owner_id>"
    _, setting_name, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id
        setting_info = next((s for s in DEFAULT_SETTINGS if s[0] == setting_name), None)
        if not setting_info:
            await callback.answer("Настройка не найдена!")
            return

        raw_value = await db.get_setting(chat_id, setting_name)
        if isinstance(raw_value, str):
            new_value = raw_value.lower() != "true"
        else:
            new_value = not bool(raw_value)

        await db.set_setting(chat_id, setting_name, new_value)

        await callback.message.edit_text(
            f"⚙️ <b>Настройка: {setting_name}</b>\n"
            f"📒 <b>Описание:</b> {setting_info[4]}\n"
            f"🔢 Текущее значение: {new_value}",
            reply_markup=kb_settings.setting_options_keyboard(
                setting_name, new_value, owner_id=owner_id
            ),
            parse_mode=ParseMode.HTML,
        )
        await callback.answer(f"Настройка изменена: {'Вкл' if new_value else 'Выкл'}")
    except TelegramBadRequest:
        pass
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("change_int:"))
async def change_int_setting(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "change_int:<name>:<change>:<owner_id>"
    _, setting_name, change, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id
        current_value = int(await db.get_setting(chat_id, setting_name))

        new_value = current_value + 1 if change == "+1" else max(0, current_value - 1)

        await db.set_setting(chat_id, setting_name, new_value)
        # повторно открыть настройку
        await open_setting(callback, bot, db)
        await callback.answer(f"Значение изменено: {new_value}")
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("select_option:"))
async def select_option(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "select_option:<name>:<option>:<owner_id>"
    _, setting_name, option, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        chat_id = callback.message.chat.id
        await db.set_setting(chat_id, setting_name, option)
        await open_setting(callback, bot, db)
        await callback.answer(f"Выбрано: {option}")
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.callback_query(F.data.startswith("input_"))
async def request_input(callback: CallbackQuery, bot: Bot, state: FSMContext):
    # callback.data = "input_<type>:<name>:<owner_id>"
    parts = callback.data.split(":")
    input_type = parts[0].split("_")[1]
    setting_name = parts[1]
    owner_id = int(parts[2])

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Вам сюда нельзя!", show_alert=True)
        return

    try:
        await state.update_data(
            setting_name=setting_name, input_type=input_type, owner_id=owner_id
        )
        await state.set_state(SettingsStates.waiting_for_input)
        await callback.message.answer("✍️ Введите новое значение:")
        await callback.answer()
    except Exception:
        await error_report(callback.message, bot, "settings", format_exc())


@settings_router.message(SettingsStates.waiting_for_input)
async def handle_setting_input(
    message: Message, bot: Bot, state: FSMContext, db: Database
):
    data = await state.get_data()
    setting_name = data["setting_name"]
    input_type = data["input_type"]
    owner_id = data["owner_id"]

    # Проверяем, что вводит тот же пользователь
    if message.from_user.id != owner_id:
        await message.reply("❌ Вы не автор этой операции.")
        return

    try:
        if input_type == "int":
            value = int(message.text)
        elif input_type == "float":
            value = float(message.text)
        else:
            value = message.text
    except ValueError:
        await message.reply("❌ Некорректный формат. Попробуйте снова.")
        return

    try:
        await db.set_setting(message.chat.id, setting_name, value)
        await message.reply(f"✅ Значение для {setting_name} успешно обновлено!")
        await state.clear()
    except Exception:
        await error_report(message, bot, "settings", format_exc())


@settings_router.message(
    Command("restore_default_settings"),
    CooldownFilter("restore_default_settings", 300),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
)
async def cmd_restore_settings(message: Message, bot: Bot, db: Database):
    try:
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
    except Exception:
        await error_report(message, bot, "restore_default_settings", format_exc())


@settings_router.callback_query(F.data.startswith("restore_default_settings:"))
async def callback_restore_settings(callback: CallbackQuery, bot: Bot, db: Database):
    # callback.data = "restore_default_settings:<yes/no>:<owner_id>"
    _, answer, owner_id_str = callback.data.split(":")
    owner_id = int(owner_id_str)

    if callback.from_user.id != owner_id:
        await callback.answer(
            "❌ Комару не разрешает отвечать на чужие колбэки", show_alert=True
        )
        return

    try:
        if answer == "no":
            await callback.answer("⛔️ Отменено")
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                await callback.answer("📛 У меня не получилось удалить своё сообщение")
        else:
            await db.restore_chat_settings(callback.message.chat.id)
            await callback.answer("✅ Успешно сброшено")
            try:
                await callback.message.delete()
            except TelegramBadRequest:
                await callback.answer("📛 У меня не получилось удалить своё сообщение")
    except Exception:
        await error_report(
            callback.message, bot, "restore_default_settings", format_exc()
        )
