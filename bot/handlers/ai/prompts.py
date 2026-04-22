import traceback
from html import escape
from traceback import format_exc

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.database import Database
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.keyboards.callback_data import PromptsMenuCallback
from bot.keyboards.prompts_keyboard import *
from bot.utils.aio_tools import error_report


class AddPromptStates(StatesGroup):
    choosing_title = State()
    choosing_content = State()


class PromptEditStates(StatesGroup):
    editing_title = State()
    editing_content = State()


class ImportPromptStates(StatesGroup):
    entering_id = State()


prompts_router = Router()


@prompts_router.message(
    Command("prompts"), FuncEnabled("user_prompts"), CooldownFilter("prompts", 15)
)
async def cmd_prompts(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id  # type: ignore
        keyboard = make_pmenu_keyboard(user_id)
        await message.reply("📚 Выберите опцию:", reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "prompts", traceback.format_exc())


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "list_prompts"))
async def cb_prompts_list(
    query: CallbackQuery, callback_data: PromptsMenuCallback, bot: Bot, db: Database
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        prompts = await db.get_all_prompts(callback_data.user_id)

        if not prompts:
            return await query.message.edit_text(
                "📭 Промптов нет.",
                reply_markup=make_pmenu_back_keyboard(callback_data.user_id),
            )

        builder = InlineKeyboardBuilder()
        for p in prompts:
            pub = "🌐" if p["is_public"] else "🔒"
            builder.button(
                text=f"{pub} {p['title']}",
                callback_data=PromptsMenuCallback(
                    action="manage", user_id=callback_data.user_id, prompt_id=p["id"]
                ),
            )
        builder.button(
            text="◀️ В главное меню",
            callback_data=PromptsMenuCallback(
                action="show_menu", user_id=callback_data.user_id
            ),
        )
        builder.adjust(1)

        await query.message.edit_text(
            "📋 <b>Выберите промпт для настройки:</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_prompts_list",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "show_menu"))
async def cb_prompts_to_menu(
    query: CallbackQuery, callback_data: PromptsMenuCallback, bot: Bot
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        await query.message.edit_text(
            "📚 Выберите опцию:",
            reply_markup=make_pmenu_keyboard(callback_data.user_id),
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_prompts_list",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "manage"))
async def cb_manage_prompt(
    query: CallbackQuery, callback_data: PromptsMenuCallback, bot: Bot, db: Database
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        prompt = await db.get_prompt(callback_data.prompt_id)
        if not prompt:
            await query.answer("❌ Промпт не найден", show_alert=True)
            return

        text = (
            f"🛠 <b>Настройка промпта:</b> <code>{escape(prompt['title'])}</code>\n\n"
            f"🆔 ID промпта: <code>{prompt['id']}</code>\n"
            f"🌐 Доступ: {'Публичный' if prompt['is_public'] else 'Приватный'}\n"
            f"📄 Текст: <blockquote expandable>{escape(prompt['content'][:150])}...</blockquote>"
        )

        await query.message.edit_text(
            text,
            reply_markup=make_prompt_manage_keyboard(
                callback_data.user_id, prompt["id"]
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_manage_prompt",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "tgpub"))
async def cb_toggle_prompt_visibility(
    query: CallbackQuery, callback_data: PromptsMenuCallback, bot: Bot, db: Database
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        current_prompt = await db.get_prompt(callback_data.prompt_id)
        if not current_prompt:
            await query.answer("❌ Промпт не найден", show_alert=True)
            return

        new_status = not current_prompt["is_public"]
        await db.update_prompt(
            callback_data.prompt_id, callback_data.user_id, is_public=new_status
        )

        await query.answer(
            f"✅ Статус изменен на: {'Публичный' if new_status else 'Приватный'}"
        )
        await cb_manage_prompt(query, callback_data, bot, db)
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_toggle_visibility",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "delpr"))
async def cb_delete_prompt(
    query: CallbackQuery, callback_data: PromptsMenuCallback, bot: Bot, db: Database
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        current_prompt = await db.get_prompt(callback_data.prompt_id)
        if not current_prompt:
            await query.answer("❌ Промпт не найден", show_alert=True)
            return

        await db.remove_prompt(callback_data.prompt_id)
        await query.answer(f"✅ Промпт удалён", show_alert=True)
        await query.message.edit_text(
            "📚 Выберите опцию:",
            reply_markup=make_pmenu_keyboard(callback_data.user_id),
        )

    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_toggle_visibility",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "edt"))
async def cb_edit_title_start(
    query: CallbackQuery,
    callback_data: PromptsMenuCallback,
    bot: Bot,
    db: Database,
    state: FSMContext,
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        prompt = await db.get_prompt(callback_data.prompt_id)
        if not prompt:
            await query.answer("❌ Промпт не найден", show_alert=True)
            return

        await state.set_state(PromptEditStates.editing_title)
        await state.update_data(prompt_id=callback_data.prompt_id, user_id=user_id)

        await query.answer()
        await query.message.edit_text(
            f"✏️ <b>Редактирование названия</b>\n\n"
            f"🔡 Текущее название: <code>{escape(prompt['title'])}</code>\n\n"
            f"🆕 Отправьте новое название:",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_edit_title_start",
                traceback=format_exc(),
            )


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "edc"))
async def cb_edit_content_start(
    query: CallbackQuery,
    callback_data: PromptsMenuCallback,
    bot: Bot,
    db: Database,
    state: FSMContext,
):
    try:
        user_id = query.from_user.id
        if callback_data.user_id != user_id:
            await query.answer("❌ Не ваш коллбэк", show_alert=True)
            return

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        prompt = await db.get_prompt(callback_data.prompt_id)
        if not prompt:
            await query.answer("❌ Промпт не найден", show_alert=True)
            return

        await state.set_state(PromptEditStates.editing_content)
        await state.update_data(prompt_id=callback_data.prompt_id, user_id=user_id)

        await query.answer()
        await query.message.edit_text(
            f"📄 <b>Редактирование текста</b>\n\n"
            f"🔡 Текущий текст: <blockquote expandable>{escape(prompt['content'][:200])}...</blockquote>\n\n"
            f"🆕 Отправьте новый текст:",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(
                message=query.message,
                bot=bot,
                command="cb_edit_content_start",
                traceback=format_exc(),
            )


@prompts_router.message(StateFilter(PromptEditStates.editing_title))
async def process_edit_title(
    message: Message, state: FSMContext, bot: Bot, db: Database
):
    try:
        if not message.text:
            await message.reply("❌ Пожалуйста, отправьте текст")
            return

        data = await state.get_data()
        prompt_id = data.get("prompt_id")
        user_id = data.get("user_id")

        if not prompt_id or not user_id:
            await state.clear()
            raise RuntimeError("📛 Куда-то потерялись данные")

        await db.update_prompt(prompt_id, user_id, title=message.text)
        await state.clear()

        await message.reply(
            f"✅ Название промпта обновлено на: <code>{escape(message.text)}</code>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "process_edit_title", traceback.format_exc())


@prompts_router.message(StateFilter(PromptEditStates.editing_content))
async def process_edit_content(
    message: Message, state: FSMContext, bot: Bot, db: Database
):
    try:
        if not message.text:
            await message.reply("❌ Пожалуйста, отправьте текст")
            return

        data = await state.get_data()
        prompt_id = data.get("prompt_id")
        user_id = data.get("user_id")

        if not prompt_id or not user_id:
            await state.clear()
            raise RuntimeError("📛 Куда-то потерялись данные")

        await db.update_prompt(prompt_id, user_id, content=message.text)
        await state.clear()

        await message.reply(f"✅ Текст промпта обновлен", parse_mode=ParseMode.HTML)
    except Exception:
        await error_report(message, bot, "process_edit_content", traceback.format_exc())


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "add_pr"))
async def cb_add_prompt_start(
    query: CallbackQuery,
    bot: Bot,
    callback_data: PromptsMenuCallback,
    state: FSMContext,
):
    try:
        if callback_data.user_id != query.from_user.id:
            return await query.answer("❌ Не ваш коллбэк", show_alert=True)

        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        await state.set_state(AddPromptStates.choosing_title)
        await state.update_data(user_id=callback_data.user_id)

        await query.message.edit_text(
            "🆕 <b>Создание нового промпта</b>\n\n"
            "🔠 Отправьте название (одно слово, латиница/кириллица).\n"
            "📞 Оно будет триггером для вызова.\n\n"
            "❌ <code>/cancel</code> для отмены",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        if isinstance(query.message, Message):
            await error_report(query.message, bot, "cb_add_prompt_start", format_exc())


@prompts_router.message(StateFilter(AddPromptStates.choosing_title))
async def process_add_title(
    message: Message, bot: Bot, state: FSMContext, db: Database
):
    try:
        if not message.text:
            await message.reply("❌ Пожалуйста, отправьте текст")
            return

        text = message.text.strip()
        if text.lower() == "/cancel":
            await state.clear()
            return await message.reply("✅ Отменено. Используйте /prompts для меню.")

        if len(text.split()) != 1:
            return await message.reply("❌ Название должно состоять из одного слова.")

        user_id = message.from_user.id  # type: ignore
        if await db.get_prompt_by_title(text, user_id):
            return await message.reply("❌ Промпт с таким именем уже существует.")

        await state.update_data(title=text)
        await state.set_state(AddPromptStates.choosing_content)
        await message.reply(
            f"✏️ Название <code>{escape(text)}</code> принято.\n📝 Теперь отправьте содержимое промпта:",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "process_add_title", format_exc())


@prompts_router.message(StateFilter(AddPromptStates.choosing_content))
async def process_add_content(
    message: Message, bot: Bot, state: FSMContext, db: Database
):
    try:
        if not message.text and not message.document:
            await message.reply("❌ Пожалуйста, отправьте текст или текстовый файл")
            return

        if message.document and message.document.mime_type != "text/plain":
            filename = (message.document.file_name or "").lower()
            if not filename.endswith((".txt", ".text")):
                await message.reply(
                    "❌ Пожалуйста, отправьте **текстовый** файл (.txt)"
                )
                return

        if message.text:
            text = message.text.strip()
        else:
            doc = message.document
            if not doc:
                await message.reply("❌ Ошибка: документ не найден")
                return

            file_info = await bot.get_file(doc.file_id)
            if not file_info.file_path:
                await message.reply("❌ Ошибка: не удалось получить путь файла")
                return

            downloaded_file = await bot.download_file(file_info.file_path)
            if not downloaded_file:
                await message.reply("❌ Ошибка: не удалось скачать файл")
                return

            try:
                text = downloaded_file.read().decode("utf-8")
            except UnicodeDecodeError:
                downloaded_file.seek(0)
                try:
                    text = downloaded_file.read().decode("windows-1251")
                except:
                    await message.reply(
                        "❌ Не удалось прочитать файл. Убедитесь, что он в кодировке UTF-8 или Windows-1251."
                    )
                    return
            finally:
                downloaded_file.close()

        if text.lower() == "/cancel":
            await state.clear()
            return await message.reply("✅ Отменено.")

        data = await state.get_data()
        user_id = message.from_user.id  # type: ignore
        title = data["title"]

        prompt_id = await db.add_prompt(user_id, title, text)
        await state.clear()

        builder = InlineKeyboardBuilder()
        builder.button(
            text="⚙️ Настроить этот промпт",
            callback_data=PromptsMenuCallback(
                action="manage", user_id=user_id, prompt_id=prompt_id
            ),
        )
        builder.button(
            text="📚 В меню",
            callback_data=PromptsMenuCallback(action="show_menu", user_id=user_id),
        )

        await message.reply(
            f"✅ Промпт <b>{escape(title)}</b> успешно создан!\n"
            f"🆔 ID: <code>{prompt_id}</code>",
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "process_add_content", format_exc())


@prompts_router.callback_query(PromptsMenuCallback.filter(F.action == "import_pr"))
async def cb_import_prompt_start(query: CallbackQuery, bot: Bot, state: FSMContext):
    try:
        if not isinstance(query.message, Message) or not query.message.text:
            await query.answer("❌ Сообщение недоступно или удалено", show_alert=True)
            return

        await state.set_state(ImportPromptStates.entering_id)
        await query.message.edit_text(
            "📥 <b>Импорт публичного промпта</b>\n\n"
            "🆔 Пришлите ID промпта , чтобы добавить его к себе.\n"
            "📌 <i>Промпт должен быть отмечен автором как публичный.</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(query.message, bot, "import_start", format_exc())  # type: ignore


@prompts_router.message(StateFilter(ImportPromptStates.entering_id))
async def process_import_id(
    message: Message, state: FSMContext, db: Database, bot: Bot
):
    try:
        if not message.text:
            await message.reply("❌ Пожалуйста, отправьте текст")
            return

        prompt_id = message.text.strip()
        user_id = message.from_user.id  # type: ignore

        prompt = await db.get_prompt(prompt_id)

        if not prompt:
            return await message.reply("❌ Промпт с таким ID не найден.")

        if not prompt["is_public"] and prompt["user_id"] != user_id:
            return await message.reply(
                "🔒 Этот промпт является приватным. Автор не разрешил его копирование."
            )

        if await db.get_prompt_by_title(prompt["title"], user_id):
            return await message.reply(
                f"❌ У вас уже есть промпт с названием <b>{escape(prompt['title'])}</b>. "
                f"Сначала удалите или переименуйте старый.",
                parse_mode="HTML",
            )

        new_id = await db.add_prompt(user_id, prompt["title"], prompt["content"])
        await state.clear()

        await message.reply(
            f"✅ Промпт <b>{escape(prompt['title'])}</b> успешно импортирован!\n"
            f"🆔 Ваш новый ID: <code>{new_id}</code>",
            reply_markup=make_pmenu_keyboard(user_id),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "process_import_id", format_exc())
