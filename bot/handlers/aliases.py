import json
import re
import traceback

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.premium_filter import PremiumFilter
from bot.keyboards.aliases_keyboard import (
    make_aliases_back_keyboard,
    make_aliases_list_keyboard,
    make_aliases_menu_keyboard,
)
from bot.keyboards.callback_data import AliasMenuCallback
from bot.utils.aio_tools import error_report

aliases_router = Router()

MAX_ALIASES = 100
ALIAS_RE = re.compile(r"^[а-яёА-ЯЁa-zA-Z0-9_\-]{1,32}$")
FORBIDDEN_TARGETS = {"aliases"}

DEFAULT_PRESET: dict[str, str] = {
    "отмена": "cancel",
    "ии": "ai",
    "промпты": "prompts",
    "кот": "cat",
    "погода": "weather",
    "бонум": "bonum",
    "дуэль": "duel",
    "кейсы": "cases",
    "инфо": "info",
    "премиум": "premium",
    "настройки": "settings",
}


class AddAliasStates(StatesGroup):
    choosing_alias = State()
    choosing_target = State()


async def _get_aliases(db: Database, user_id: int) -> dict[str, str]:
    aliases = await db.get_global_user_param(user_id, "aliases")
    if not aliases:
        return {}
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except Exception:
            return {}
    return aliases if isinstance(aliases, dict) else {}


async def _save_aliases(db: Database, user_id: int, aliases: dict[str, str]) -> None:
    await db.set_global_user_param(
        user_id, "aliases", json.dumps(aliases, ensure_ascii=False)
    )


class AliasMiddleware:  # Святые угодники, не бейте меня за это
    async def __call__(self, handler, event, data):
        if not isinstance(event, Message):
            return await handler(event, data)
        text: str = event.text or ""
        if not text:
            return await handler(event, data)
        parts = text.split(None, 1)
        raw_cmd = parts[0].lstrip("/").split("@")[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        db: Database | None = data.get("db")
        if db is None or event.from_user is None:
            return await handler(event, data)
        is_premium = await db.is_premium_user(event.from_user.id)
        if not is_premium:
            return await handler(event, data)
        aliases = await _get_aliases(db, event.from_user.id)
        if raw_cmd not in aliases:
            return await handler(event, data)
        real_cmd = aliases[raw_cmd]
        await db.log_command(event.from_user.id, "alias")
        new_text = f"/{real_cmd}" + (f" {rest}" if rest else "")
        object.__setattr__(event, "text", new_text)
        return await handler(event, data)


@aliases_router.message(
    Command("aliases"), PremiumFilter(), CooldownFilter("aliases", 5)
)
async def cmd_alias_list(message: Message, bot: Bot, db: Database):
    try:
        if message.from_user is None:
            return
        await message.reply(
            "🔗 Выберите опцию:",
            reply_markup=make_aliases_menu_keyboard(message.from_user.id),
        )
    except Exception:
        await error_report(message, bot, "aliases", traceback.format_exc())


async def _get_callback_message(
    query: CallbackQuery, callback_data: AliasMenuCallback
) -> Message | None:
    if callback_data.user_id != query.from_user.id:
        await query.answer("❌ Не ваш коллбэк", show_alert=True)
        return None
    if not isinstance(query.message, Message):
        await query.answer("❌ Сообщение недоступно", show_alert=True)
        return None
    return query.message


@aliases_router.callback_query(AliasMenuCallback.filter(F.action == "menu"))
async def cb_aliases_menu(
    query: CallbackQuery,
    callback_data: AliasMenuCallback,
    state: FSMContext,
):
    callback_message = await _get_callback_message(query, callback_data)
    if callback_message is None:
        return
    await state.clear()
    await callback_message.edit_text(
        "🔗 Выберите опцию:",
        reply_markup=make_aliases_menu_keyboard(callback_data.user_id),
    )
    await query.answer()


@aliases_router.callback_query(AliasMenuCallback.filter(F.action == "list"))
async def cb_aliases_list(
    query: CallbackQuery, callback_data: AliasMenuCallback, db: Database
):
    callback_message = await _get_callback_message(query, callback_data)
    if callback_message is None:
        return
    aliases = await _get_aliases(db, callback_data.user_id)
    if not aliases:
        await callback_message.edit_text(
            "📭 У вас пока нет алиасов.",
            reply_markup=make_aliases_back_keyboard(callback_data.user_id),
        )
    else:
        await callback_message.edit_text(
            f"📋 <b>Ваши алиасы</b> ({len(aliases)}/{MAX_ALIASES}):\n\n"
            "Нажмите на алиас, чтобы удалить его.",
            reply_markup=make_aliases_list_keyboard(callback_data.user_id, aliases),
            parse_mode=ParseMode.HTML,
        )
    await query.answer()


@aliases_router.callback_query(AliasMenuCallback.filter(F.action == "delete"))
async def cb_alias_delete(
    query: CallbackQuery, callback_data: AliasMenuCallback, db: Database
):
    callback_message = await _get_callback_message(query, callback_data)
    if callback_message is None:
        return
    aliases = await _get_aliases(db, callback_data.user_id)
    if callback_data.alias not in aliases:
        await query.answer("❌ Алиас не найден", show_alert=True)
        return
    del aliases[callback_data.alias]
    await _save_aliases(db, callback_data.user_id, aliases)
    await query.answer("✅ Алиас удалён", show_alert=True)
    if aliases:
        await callback_message.edit_text(
            f"📋 <b>Ваши алиасы</b> ({len(aliases)}/{MAX_ALIASES}):\n\n"
            "Нажмите на алиас, чтобы удалить его.",
            reply_markup=make_aliases_list_keyboard(callback_data.user_id, aliases),
            parse_mode=ParseMode.HTML,
        )
    else:
        await callback_message.edit_text(
            "📭 У вас пока нет алиасов.",
            reply_markup=make_aliases_back_keyboard(callback_data.user_id),
        )


@aliases_router.callback_query(AliasMenuCallback.filter(F.action == "preset"))
async def cb_aliases_preset(
    query: CallbackQuery, callback_data: AliasMenuCallback, db: Database
):
    callback_message = await _get_callback_message(query, callback_data)
    if callback_message is None:
        return
    aliases = await _get_aliases(db, callback_data.user_id)
    added = 0
    for alias, target in DEFAULT_PRESET.items():
        if alias not in aliases and len(aliases) < MAX_ALIASES:
            aliases[alias] = target
            added += 1
    if added:
        await _save_aliases(db, callback_data.user_id, aliases)
    await query.answer(
        f"✅ Добавлено алиасов: {added}" if added else "ℹ️ Пресет уже загружен",
        show_alert=True,
    )


@aliases_router.callback_query(AliasMenuCallback.filter(F.action == "add"))
async def cb_alias_add_start(
    query: CallbackQuery,
    callback_data: AliasMenuCallback,
    state: FSMContext,
):
    callback_message = await _get_callback_message(query, callback_data)
    if callback_message is None:
        return
    await state.set_state(AddAliasStates.choosing_alias)
    await state.update_data(user_id=callback_data.user_id)
    await callback_message.edit_text(
        "➕ Отправьте название алиаса.",
        reply_markup=make_aliases_back_keyboard(callback_data.user_id),
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


@aliases_router.message(StateFilter(AddAliasStates.choosing_alias))
async def process_alias_name(message: Message, state: FSMContext):
    alias = (message.text or "").strip().lstrip("/").lower()
    if not ALIAS_RE.fullmatch(alias):
        await message.reply("❌ Некорректный алиас. Попробуйте ещё раз.")
        return
    await state.update_data(alias=alias)
    await state.set_state(AddAliasStates.choosing_target)
    await message.reply(
        f"🔗 Алиас <code>{alias}</code>. Теперь отправьте команду.",
        parse_mode=ParseMode.HTML,
    )


@aliases_router.message(StateFilter(AddAliasStates.choosing_target))
async def process_alias_target(message: Message, state: FSMContext, db: Database):
    if message.from_user is None:
        return
    target = (message.text or "").strip().lstrip("/").lower()
    if not ALIAS_RE.fullmatch(target):
        await message.reply("❌ Название команды некорректно.")
        return
    if target in FORBIDDEN_TARGETS:
        await message.reply("❌ Нельзя создать алиас для этой команды.")
        return
    data = await state.get_data()
    alias = data.get("alias")
    user_id = data.get("user_id")
    if not isinstance(alias, str) or not isinstance(user_id, int):
        await state.clear()
        await message.reply("❌ Не удалось сохранить алиас. Откройте меню заново.")
        return
    if user_id != message.from_user.id:
        await state.clear()
        await message.reply("❌ Не удалось сохранить алиас. Откройте меню заново.")
        return
    aliases = await _get_aliases(db, user_id)
    if len(aliases) >= MAX_ALIASES and alias not in aliases:
        await state.clear()
        await message.reply(f"❌ Достигнут лимит алиасов ({MAX_ALIASES}).")
        return
    aliases[alias] = target
    await _save_aliases(db, user_id, aliases)
    await state.clear()
    await message.reply(
        f"✅ Алиас добавлен: <code>{alias}</code> → <code>/{target}</code>",
        reply_markup=make_aliases_menu_keyboard(user_id),
        parse_mode=ParseMode.HTML,
    )
