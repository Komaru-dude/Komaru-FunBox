import asyncio
import math
import os
import random
import traceback
import uuid
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import IS_TEST, logger
from bot.database.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.filters.func_filter import FuncEnabled
from bot.keyboards.duel_keyboard import (
    DuelCallback,
    make_duel_actions_keyboard,
    make_duel_keyboard,
)
from bot.keyboards.math_keyboard import make_math_kb
from bot.keyboards.shop_keyboard import ShopCallback, make_shop_keyboard
from bot.utils.aio_tools import error_report, get_user_id
from bot.utils.global_storage import (
    duel_sessions,
    duel_sessions_lock,
    eco_config,
    shop_config,
)

eco_router = Router()


@eco_router.message(
    Command("work"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled("economy"),
    CooldownFilter(command="work", cooldown=eco_config["work_timeout"]),
)
async def cmd_work(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        current_bal = await db.get_global_user_param(user_id, "money")
        work_tools_msg = ""

        min_income = eco_config["min_work_income"]
        max_income = eco_config["max_work_income"]
        current_income = random.randint(min_income, max_income)
        has_work_tools = await db.has_valid_item(user_id, "work_tools")

        if has_work_tools:
            bonus = round(current_income * 0.25, 2)
            current_income = current_income + bonus
            work_tools_msg = f"🧑‍🏭 Использование рабочих инструментов принесло вам: {bonus} {eco_config['currency_sign']}\n"

        new_bal = current_bal + current_income
        new_bal = round(new_bal, 2)
        await db.set_global_user_param(user_id, "money", new_bal)
        msg = await message.reply(
            f"👨‍💻 Вы заработали: {current_income}\n{work_tools_msg}{eco_config["currency_sign"]} Ваш новый баланс: {new_bal}"
        )
    except Exception:
        await db.reset_cooldown(user_id, "work")
        await error_report(message, bot, "work", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


class MathStates(StatesGroup):
    choosing_difficulty = State()
    waiting_for_answer = State()


@eco_router.message(
    Command("math"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled("economy"),
    CooldownFilter("math", eco_config["math_timeout"]),
)
async def cmd_math(message: Message, bot: Bot, db: Database, state: FSMContext):
    try:
        kb = make_math_kb(message.from_user.id)
        msg = await message.answer("📊 Выберите уровень сложности:", reply_markup=kb)
        await state.set_state(MathStates.choosing_difficulty)
        await state.update_data(menu_msg_id=msg.message_id)

    except Exception:
        await db.reset_cooldown(message.from_user.id, "math")
        await error_report(message, bot, "math", traceback.format_exc())


@eco_router.callback_query(MathStates.choosing_difficulty, F.data.startswith("math_"))
async def process_difficulty(
    callback: CallbackQuery, bot: Bot, db: Database, state: FSMContext
):
    try:
        difficulty = callback.data.split("_")[1]
        op = None
        a, b = 0, 0

        if difficulty == "easy":
            op = random.choice(["+", "-", "*"])
            if op == "+":
                a = random.randint(1, 50)
                b = random.randint(1, 50)
            elif op == "-":
                a = random.randint(20, 50)
                b = random.randint(1, a - 1)
            else:  # умножение
                a = random.randint(1, 10)
                b = random.randint(1, 10)

        elif difficulty == "medium":
            op = random.choice(["+", "-", "*", "/"])
            if op in ["+", "-"]:
                a = random.randint(10, 100)
                b = random.randint(10, 100)
                if op == "-" and a < b:
                    a, b = b, a
            elif op == "*":
                a = random.randint(5, 25)
                b = random.randint(5, 25)
            else:  # деление
                b = random.randint(2, 12)
                a = b * random.randint(3, 15)

        else:  # hard
            op = random.choice(["+", "-", "*", "/"])
            if op in ["+", "-"]:
                a = random.randint(100, 1000)
                b = random.randint(100, 1000)
                if op == "-" and a < b:
                    a, b = b, a
            elif op == "*":
                a = random.randint(50, 150)
                b = random.randint(50, 150)
            else:  # деление
                b = random.randint(10, 100)
                a = b * random.randint(10, 100)

        expr = f"{a} {op} {b}" if op != "/" else f"{a} ÷ {b}"
        if op == "/":
            answer = a // b
        else:
            answer = int(eval(expr))

        await state.update_data(answer=answer, difficulty=difficulty)
        await callback.message.edit_text(f"🧠 Пример:\n❓ Сколько будет {expr}?")
        await state.set_state(MathStates.waiting_for_answer)

    except Exception:
        await db.reset_cooldown(callback.from_user.id, "math")
        await error_report(
            callback.message, bot, "math_difficulty", traceback.format_exc()
        )


@eco_router.message(F.text, MathStates.waiting_for_answer)
async def process_math_answer(
    message: Message, bot: Bot, db: Database, state: FSMContext
):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        difficulty = data.get("difficulty", "easy")
        correct = data.get("answer")
        money = await db.get_global_user_param(user_id, "money")

        try:
            user_answer = int(message.text.strip())
        except ValueError:
            msg = await message.reply("❌ Введите целое число или /cancel для отмены")
            return

        if user_answer == correct:
            reward_range = eco_config["math_rewards"].get(difficulty, [10, 30])
            reward = random.randint(*reward_range)
            final_money = money + reward
            msg = await message.reply(
                f"✅ Верно!\n💵 Вы получили {eco_config['currency_sign']} {reward}.\n{eco_config['currency_sign']} Текущий баланс: {final_money} {eco_config['currency_sign']}"
            )
        else:
            fine_range = eco_config["math_fines"].get(difficulty, [5, 15])
            fine = random.randint(*fine_range)
            final_money = money - fine
            msg = await message.reply(
                f"❌ Неверно! Правильный ответ: {correct}.\n💸 Штраф: {eco_config['currency_sign']} {fine}.\n{eco_config['currency_sign']} Текущий баланс: {final_money} {eco_config['currency_sign']}"
            )

        await db.set_global_user_param(user_id, "money", final_money)
        await state.clear()

    except Exception:
        await db.reset_cooldown(message.from_user.id, "math")
        await error_report(message, bot, "math_answer", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(
    Command("steal"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled("economy"),
    CooldownFilter(command="steal", cooldown=eco_config["steal_timeout"]),
)
async def cmd_steal(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        current_bal = await db.get_global_user_param(user_id, "money")
        if current_bal < eco_config["max_steal_penalty"] / 2:
            msg = await message.reply(
                f"❌ Вам нужно иметь на балансе хотя бы половину от максимальной суммы штрафа ({eco_config["currency_sign"]}{eco_config['max_steal_penalty'] / 2})"
            )
            await db.reset_cooldown(user_id, "steal")
            return

        min_income = eco_config["min_steal_income"]
        max_income = eco_config["max_steal_income"]
        current_income = random.randint(min_income, max_income)

        min_penalty = eco_config["min_steal_penalty"]
        max_penalty = eco_config["max_steal_penalty"]
        current_penalty = random.randint(min_penalty, max_penalty)

        fail_percent = eco_config["steal_fail_percent"]

        has_fake_passport = await db.has_valid_item(user_id, "fake_passport")

        if has_fake_passport:
            fail_percent = max(0, fail_percent - 50)  # уменьшаем шанс неудачи на 20%
            await db.use_item(user_id, "fake_passport")
            passport_used_msg = (
                "🛡 Фейковый паспорт был использован, шанс неудачи снижен!"
            )
        else:
            passport_used_msg = ""

        if random.randint(1, 100) <= fail_percent:
            new_bal = current_bal - current_penalty
            new_bal = round(new_bal, 2)
            msg = await message.reply(
                f"😔 Вам не повезло.\n🧨 Вы потеряли: {current_penalty}\n{eco_config['currency_sign']} Ваш новый баланс: {new_bal}\n{passport_used_msg}"
            )
        else:
            new_bal = current_bal + current_income
            new_bal = round(new_bal, 2)
            msg = await message.reply(
                f"🤑 Повезло!\n💡 Вы заработали: {current_income}\n{eco_config['currency_sign']} Ваш новый баланс: {new_bal}\n{passport_used_msg}"
            )

        await db.set_global_user_param(user_id, "money", new_bal)

    except Exception:
        await db.reset_cooldown(user_id, "steal")
        await error_report(message, bot, "steal", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(
    Command("rob"),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    FuncEnabled("economy"),
    CooldownFilter(command="rob", cooldown=eco_config["rob_timeout"]),
)
async def cmd_rob(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        split_text = message.text.split()
        target_id, get_id_error = await get_user_id(message)
        protection_note = ""
        is_successful = None
        rich_fail_note = ""

        if user_id == target_id:
            msg = await message.reply("❌ Нельзя ограбить самого себя")
            return

        if len(split_text) < 2 and not message.reply_to_message:
            msg = await message.reply(
                "❌ Требуется упоминание/ответ на сообщение пользователя."
            )
            await db.reset_cooldown(user_id, "rob")
            return

        if get_id_error:
            msg = await message.reply("❌ Не удалось получить user_id!")
            await db.reset_cooldown(user_id, "rob")
            return

        # Получение баланса
        user_cash = await db.get_global_user_param(user_id, "money")
        user_bank = await db.get_global_user_param(user_id, "bank")
        user_total = user_cash + user_bank

        if user_total < 1000:
            await message.reply(
                f"📛 Ваш баланс должен быть более 1000 {eco_config["currency_sign"]}"
            )
            return
        if user_total < 5000:
            await message.reply(
                "⚠️ При вашем балансе менее 5000💰 ограбления нерентабельны!"
            )

        target_cash = await db.get_global_user_param(target_id, "money")
        target_bank = await db.get_global_user_param(target_id, "bank")
        target_total = target_cash + target_bank
        rob_max_limit = user_total * 0.15

        if target_cash < 0 and target_bank <= 0:
            msg = await message.reply("❌ У цели нет средств (ни налички, ни в банке)")
            await db.reset_cooldown(user_id, "rob")
            return

        if target_total < eco_config["min_rob_amount"]:
            msg = await message.reply("❌ У цели недостаточно средств для ограбления")
            await db.reset_cooldown(user_id, "rob")
            return

        if target_total < 3000:
            await message.reply(
                "⚠️ При балансе цели менее 3000💰 ограбления нерентабельны!"
            )

        # Ограничение ограбления:
        # 1. Максимум 15% от общего баланса грабителя
        # 2. Максимум 15% от общего баланса жертвы
        # 3. Логарифмическое ограничение
        base_limit = min(
            user_total * 0.15,
            target_total * 0.15,
        )

        # Логарифмический множитель (ограбление топов сложнее)
        log_limit = max(1.0, math.log10(target_total + 10))
        final_limit = min(base_limit, rob_max_limit / log_limit)

        succeed_percent = random.randint(
            eco_config["rob_min_percent"], eco_config["rob_max_percent"]
        )
        rob_amount = round(target_total * (succeed_percent / 100), 2)
        rob_amount = round(min(rob_amount, final_limit), 2)

        fail_percent = eco_config["rob_fail_percent"]
        if await db.has_valid_item(target_id, "rob_protection"):
            await db.use_item(target_id, "rob_protection")
            protection_note = "🛡 У цели была активирована защита от ограблений.\n"
            fail_percent += 25

        if random.randint(1, 100) <= fail_percent:
            penalty = random.randint(
                eco_config["min_rob_penalty"], eco_config["max_rob_penalty"]
            )

            if user_cash > eco_config["rob_penalty_max_rich"]:
                penalty = penalty * eco_config["rob_penalty_mult_rich"]
                rich_fail_note = f"🆙 Ваш баланс превышает {eco_config["rob_penalty_max_rich"]} {eco_config["currency_sign"]}.\n💸 Штраф увеличен в {eco_config["rob_penalty_mult_rich"]} раз\n"

            new_cash = user_cash - penalty
            is_successful = False
            msg = await message.reply(
                protection_note
                + rich_fail_note
                + f"🚔 Вас поймали!\n📉 Штраф: {penalty}{eco_config['currency_sign']}\n💰 Новый баланс: {round(new_cash, 2)}"
            )
            await db.set_global_user_param(user_id, "money", new_cash)
        else:
            taken_cash = round(min(target_cash, rob_amount), 2)
            taken_bank = round(
                (rob_amount - taken_cash) * eco_config["rob_bank_percent"], 2
            )
            target_new_cash = round(target_cash - taken_cash, 2)
            target_new_bank = round(target_bank - taken_bank, 2)
            new_cash = user_cash + taken_cash + taken_bank
            is_successful = True

            msg = await message.reply(
                protection_note
                + f"🤑 Повезло!\n💰 Украдено: {rob_amount}{eco_config['currency_sign']}\n"
                f"💸 Из наличных: {taken_cash}, из банка: {taken_bank}\n"
                f"🎯 Новый баланс цели: {round(target_new_cash + target_new_bank, 2)}\n"
                f"💵 Ваш новый баланс: {round(new_cash, 2)}"
            )

            await db.set_global_user_param(user_id, "money", new_cash)
            await db.set_global_user_param(target_id, "money", target_new_cash)
            await db.set_global_user_param(target_id, "bank", target_new_bank)

        if await db.is_user_setting_enabled(
            user_id, "rob_notif"
        ) and not await db.is_active_user(user_id):
            non_working_rob_msg = await message.reply(
                "⚠️ У вас включена функция rob_notif, но бот не может вам написать.\n💬 Напишите боту или выключите функцию (/user_settings > уведомления > rob_notif)"
            )

        if await db.is_user_setting_enabled(
            target_id, "rob_notif"
        ) and await db.is_active_user(target_id):
            if is_successful == True:
                await bot.send_message(
                    target_id,
                    f'😵 Вас успешно ограбил <a href="tg://user?id={user_id}">{user_id}</a>!',
                    parse_mode=ParseMode.HTML,
                )
            elif is_successful == False:
                await bot.send_message(
                    target_id,
                    f'🥸 Вас попытался ограбить <a href="tg://user?id={user_id}">{user_id}</a>!',
                    parse_mode=ParseMode.HTML,
                )
            else:
                logger.warning("Переменная is_successful осталась в None")

    except ZeroDivisionError:
        profile_link = f"tg://user?id={os.getenv('OWNER_ID')}"
        msg = await message.reply(
            f'❌ Произошло деление на ноль! Обратитесь к владельцу: <a href="{profile_link}">Тык</a>',
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await db.reset_cooldown(user_id, "rob")
        await error_report(message, bot, "rob", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
                if "non_working_rob_msg" in locals():
                    await non_working_rob_msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


class Dice(StatesGroup):
    choose_bet = State()
    choose_dice = State()


@eco_router.message(
    Command("dice"),
    FuncEnabled("economy"),
    CooldownFilter(command="dice", cooldown=eco_config["dice_timeout"]),
)
async def cmd_dice(message: Message, bot: Bot, state: FSMContext):
    try:
        currency_sign = eco_config["currency_sign"]
        await message.reply(
            f"💸 Выберите ставку.\nОт {currency_sign} {eco_config["dice_min_bet"]} или {currency_sign} 0 до {currency_sign} {eco_config["dice_max_bet"]}"
        )
        await state.set_state(Dice.choose_bet)
    except Exception:
        await error_report(message, bot, "dice", traceback.format_exc())


@eco_router.message(Dice.choose_bet)
async def bet_chosen(message: Message, bot: Bot, db: Database, state: FSMContext):
    currency_sign = eco_config["currency_sign"]
    user_id = message.from_user.id
    try:
        number = round(float(message.text), 2)
        if number < eco_config["dice_min_bet"] and number != 0:
            await message.reply(
                f"❌ Минимальная ставка - {currency_sign} {eco_config['dice_min_bet']} или {currency_sign} 0"
            )
            return
        if number > eco_config["dice_max_bet"]:
            await message.reply(
                f"❌ Максимальная ставка - {currency_sign} {eco_config['dice_max_bet']}"
            )
            return

        user_bal = await db.get_global_user_param(user_id, "money")
        if user_bal < number:
            await message.reply(
                f"❌ У вас недостаточно средств для ставки {currency_sign} {number}. Ваш баланс: {currency_sign} {user_bal}"
            )
            return

        await state.update_data(bet=number)
        if number == 0:
            await db.reset_cooldown(user_id, "dice")

        builder = InlineKeyboardBuilder()
        emojis = ["🎲", "🎯", "🎳", "🏀", "⚽", "🎰"]
        rows = [emojis[i : i + 3] for i in range(0, len(emojis), 3)]
        for row in rows:
            builder.row(
                *[
                    InlineKeyboardButton(text=emoji, callback_data=f"{user_id}|{emoji}")
                    for emoji in row
                ]
            )
        await message.reply(
            '⚽️ Хорошо, выберите, что "бросите":',
            reply_markup=builder.as_markup(resize_keyboard=True),
        )
        await state.set_state(Dice.choose_dice)

    except ValueError:
        await message.reply(
            "❌ Это не число. Пожалуйста, отправьте число или /cancel для остановки"
        )
    except TypeError:
        await message.reply(
            "❌ Это не число. Пожалуйста, отправьте число или /cancel для остановки"
        )
    except Exception:
        await error_report(message, bot, "bet_chosen", traceback.format_exc())


@eco_router.callback_query(Dice.choose_dice, F.data.regexp(r"^(\d+)\|(.+)$"))
async def handle_dice_throw(
    callback: CallbackQuery, state: FSMContext, db: Database, bot: Bot
):
    try:
        user_id_str, emoji = callback.data.split("|")
        user_id = callback.from_user.id
        if int(user_id_str) != user_id:
            await callback.answer("📛 А комару запретила!", show_alert=True)
            return

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"🎲 Бросаем {emoji}...")

        dice_message = await callback.message.answer_dice(emoji=emoji)
        value = dice_message.dice.value

        data = await state.get_data()
        bet = data.get("bet")
        user_bal = await db.get_global_user_param(user_id, "money")
        currency_sign = eco_config["currency_sign"]

        win_amount = 0
        new_bal = user_bal
        msg_text = ""

        if emoji in ("🎲", "🎯", "🎳"):
            if value == 6:
                multiplier = 2.5
                msg_text = f"🎉 Большая победа! +{round(bet * multiplier, 2)} (x2.5)\n"
                win_amount = bet * multiplier
            elif value == 5:
                multiplier = 1.2
                msg_text = f"🎉 Победа! +{round(bet * multiplier, 2)} (x1.2)\n"
                win_amount = bet * multiplier
            elif value == 4:
                msg_text = f"🎲 Ничья. Ваша ставка возвращена.\n"
                win_amount = bet
            else:
                msg_text = f"💸 Проигрыш. -{bet}\n"
                win_amount = 0

        elif emoji in ("🏀", "⚽"):
            if value == 5:
                multiplier = 2.5
                msg_text = f"🏆 Гол! +{round(bet * multiplier, 2)} (x2.5)\n"
                win_amount = bet * multiplier
            elif value == 4:
                msg_text = f"⚖️ Ничья. Ваша ставка возвращена.\n"
                win_amount = bet
            else:
                msg_text = f"💸 Промах. -{bet}\n"
                win_amount = 0

        elif emoji == "🎰":
            if value == 64:
                multiplier = 7.5
                msg_text = (
                    f"🎰 ДЖЕКПОТ! Все семёрки! +{round(bet * multiplier, 2)} (x7.5)\n"
                )
                win_amount = bet * multiplier
            elif value in (1, 22, 43):
                multiplier = 2.5
                msg_text = f"✨ Почти джекпот! Все совпали! +{round(bet * multiplier, 2)} (x2.5)\n"
                win_amount = bet * multiplier
            # fmt: off
            elif value in (2,3,4,5,6,9,11,13,16,17,18,21,23,24,26,27,30,32,33,35,38,39,41,42,44,47,48,49,52,54,56,59,60,61,62,63):
                # fmt: on
                multiplier = 0.9
                msg_text = f"🥉 Слегка повезло. Есть совпавшие! +{round(bet * multiplier, 2)} (x0.9)\n"
                win_amount = bet * multiplier
            else:
                msg_text = f"💸 Проигрыш. -{bet}\n"
                win_amount = 0

        if win_amount == bet:
            new_bal = user_bal
        elif win_amount > 0:
            new_bal = round(user_bal + win_amount, 2)
        else:
            new_bal = round(user_bal - bet, 2)

        await asyncio.sleep(2)  # Ждём пока проиграется анимация

        await db.set_global_user_param(user_id, "money", new_bal)

        msg = await callback.message.answer(
            f"{msg_text}{currency_sign} Ваш текущий баланс: {new_bal}"
        )
        if IS_TEST:
            await callback.message.reply(f"🔢 Выпало значение: {value}")
            logger.debug(f"🔢 Выпало значение: {value}")

        await state.clear()

    except Exception:
        await error_report(callback, bot, "handle_dice_throw", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(callback.message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await callback.message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Command("deposit"), FuncEnabled("economy"))
async def cmd_deposit(message: Message, bot: Bot, db: Database):
    try:
        split_text = message.text.split()
        user_id = message.from_user.id
        currency_sign = eco_config["currency_sign"]

        if len(split_text) != 2:
            msg = await message.reply(
                "❌ Укажите сумму которую вы хотите положить на банковский счёт.\nНапример: <code>/deposit 150</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        to_deposit = float(split_text[1])
        user_bal = await db.get_global_user_param(user_id, "money")
        if to_deposit <= 0:
            msg = await message.reply(
                "❌ Сумма для пополнения должна быть положительной."
            )
            return
        if to_deposit > user_bal:
            msg = await message.reply(
                f"❌ Слишком большая сумма.\nВы пытаетесь перевести: {to_deposit}{currency_sign}\nУ вас есть: {user_bal}{currency_sign}"
            )
            return

        commission = round(to_deposit * 0.15, 2)
        new_to_deposit = round(to_deposit - commission, 2)
        new_user_bal = round(user_bal - to_deposit, 2)

        user_bank = await db.get_global_user_param(user_id, "bank")
        new_bank = round(user_bank + new_to_deposit, 2)

        msg = await message.reply(
            f"✅ Вы успешно пополнили банковский счёт!\n"
            f"🔥 Комиссия составила: {commission}{currency_sign}\n"
            f"💳 На счёт зачислено: {new_to_deposit}{currency_sign}\n"
            f"💰 Ваш текущий счёт: {new_bank}{currency_sign}\n"
            f"🪙 На руках осталось: {new_user_bal}{currency_sign}"
        )
        await db.set_global_user_param(user_id, "money", new_user_bal)
        await db.set_global_user_param(user_id, "bank", new_bank)

    except ValueError:
        msg = await message.reply("❌ Это не число.")
    except TypeError:
        msg = await message.reply("❌ Это не число.")
    except Exception:
        await error_report(message, bot, "deposit", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Command("withdraw"), FuncEnabled("economy"))
async def cmd_withdraw(message: Message, bot: Bot, db: Database):
    try:
        split_text = message.text.split()
        user_id = message.from_user.id
        currency_sign = eco_config["currency_sign"]

        if len(split_text) != 2:
            msg = await message.reply(
                "❌ Укажите сумму, которую вы хотите снять с банковского счёта.\n"
                "Например: <code>/withdraw 150</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        to_withdraw = float(split_text[1])
        user_bank = await db.get_global_user_param(user_id, "bank")

        if to_withdraw <= 0:
            msg = await message.reply("❌ Сумма для снятия должна быть положительной.")
            return
        if to_withdraw > user_bank:
            msg = await message.reply(
                f"❌ Слишком большая сумма.\n"
                f"Вы пытаетесь снять: {to_withdraw}{currency_sign}\n"
                f"На счету: {user_bank}{currency_sign}"
            )
            return

        new_to_withdraw = round(to_withdraw, 2)
        new_bank = round(user_bank - to_withdraw, 2)

        user_money = await db.get_global_user_param(user_id, "money")
        new_user_money = round(user_money + new_to_withdraw, 2)

        msg = await message.reply(
            f"✅ Вы успешно сняли деньги с банковского счёта!\n"
            f"🪙 На руки получено: {new_to_withdraw}{currency_sign}\n"
            f"💳 Остаток на счёте: {new_bank}{currency_sign}\n"
            f"💰 Всего у вас на руках: {new_user_money}{currency_sign}"
        )
        await db.set_global_user_param(user_id, "money", new_user_money)
        await db.set_global_user_param(user_id, "bank", new_bank)

    except ValueError:
        await message.reply("❌ Это не число.")
    except TypeError:
        await message.reply("❌ Это не число.")
    except Exception:
        await error_report(message, bot, "withdraw", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Command("transfer"), FuncEnabled("economy"))
async def cmd_transfer(message: Message, bot: Bot, db: Database):
    try:
        user_id = message.from_user.id
        currency_sign = eco_config["currency_sign"]
        args = message.text.strip().split()

        amount_str = None
        if message.reply_to_message and len(args) >= 2:
            amount_str = args[1]
        elif len(args) >= 3:
            amount_str = args[2]
        else:
            msg = await message.reply(
                "❌ Укажите пользователя и сумму.\n"
                "Пример: <code>/transfer @user 150</code>\n"
                "Или ответьте на сообщение: <code>/transfer 150</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        if not amount_str.isdigit() or int(amount_str) <= 0:
            msg = await message.reply("❌ Сумма должна быть положительным числом.")
            return
        amount = round(float(amount_str), 2)

        target_id, error = await get_user_id(message)
        if error or not target_id:
            msg = await message.reply(
                f"❌ {error or 'Не удалось определить получателя.'}"
            )
            return
        if target_id == user_id:
            msg = await message.reply("❌ Нельзя переводить валюту самому себе.")
            return

        user_balance = await db.get_global_user_param(user_id, "bank")
        if user_balance < amount:
            msg = await message.reply(
                f"❌ Недостаточно средств. Банковский баланс: {user_balance}{currency_sign}"
            )
            return

        target_balance = await db.get_global_user_param(target_id, "bank")
        new_user_balance = round(user_balance - amount, 2)
        new_target_balance = round(target_balance + amount, 2)
        await db.set_global_user_param(user_id, "bank", new_user_balance)
        await db.set_global_user_param(target_id, "bank", new_target_balance)
        msg = await message.reply(
            f"✅ Перевод {amount}{currency_sign} пользователю <code>{target_id}</code> выполнен.\n{currency_sign} Ваш новый баланс: {new_user_balance}\n{currency_sign} Новый баланс цели: {new_target_balance}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await error_report(message, bot, "transfer", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Command("top"), FuncEnabled("economy"))
async def cmd_top(message: Message, bot: Bot, db: Database):
    try:
        all_top_users = await db.get_eco_top(limit=100)
        if not all_top_users:
            msg = await message.reply("📉 Топ пользователей пуст.")
            return

        top_users = all_top_users[:10]
        currency_sign = eco_config["currency_sign"]
        top_message = "🏆 Топ 10 пользователей по балансу:\n"

        current_user_id = message.from_user.id
        user_position = None

        for idx, user in enumerate(all_top_users, start=1):
            if user["user_id"] == current_user_id:
                user_position = idx
                break

        current_user_total = 0
        try:
            user_info = await db.get_global_user(current_user_id)
            user_cash = user_info.get("money", 0.00)
            user_bank = user_info.get("bank", 0.00)
            current_user_total = round(float(user_cash) + float(user_bank), 2)
        except Exception:
            pass

        for idx, user in enumerate(top_users, start=1):
            user_id = user["user_id"]
            total = user["total"]

            try:
                user_info = await db.get_global_user(user_id)
                raw_name = f"{user_info.get('name')}".strip()
                if not raw_name:
                    raw_name = f"ID {user_id}"
            except Exception:
                raw_name = f"ID {user_id}"

            safe_name = escape(raw_name)
            is_link_enabled = await db.is_user_setting_enabled(
                user_id, "top_clickable_link"
            )

            if is_link_enabled:
                user_display = f'<a href="tg://user?id={user_id}">{safe_name}</a>'
            else:
                user_display = safe_name

            top_message += f"{idx}. {user_display} — {total} {currency_sign}\n"

        top_message += f"\n📍 Ваша позиция: {user_position if user_position is not None else '>100'}"
        top_message += f"\n💰 Ваш баланс: {current_user_total} {currency_sign}"

        msg = await message.reply(top_message, parse_mode="HTML")

    except Exception:
        await error_report(message, bot, "top", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Command("shop"), FuncEnabled("economy"))
async def cmd_shop(message: Message, bot: Bot, db: Database):
    try:
        text_lines = ["📗 Доступные товары:\n"]
        for item in shop_config:
            text_lines.append(
                f"{item['name']} — {item['price']} {eco_config['currency_sign']}\n"
                f"📝 Описание: {item.get('desc', '—')}\n"
            )
        text = "\n".join(text_lines)

        keyboard = make_shop_keyboard()
        msg = await message.reply(text, reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "shop", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(90)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.callback_query(ShopCallback.filter(F.action == "buy"))
async def shop_buy_callback(
    callback: CallbackQuery, callback_data: ShopCallback, db: Database
):
    user_id = callback.from_user.id
    item_id = callback_data.item_id

    item = next((i for i in shop_config if i["id"] == item_id), None)
    if item:
        user_bal = await db.get_global_user_param(user_id, "money")
        price = int(item["price"])
        if price > user_bal:
            await callback.answer(
                "❌ У вас недостаточно наличных для покупки предмета", show_alert=True
            )
            return
        await db.set_global_user_param(user_id, "money", user_bal - price)
        await db.add_item_to_user(user_id, item)
    else:
        await callback.answer("❌ Такого предмета не существует!", show_alert=True)

    await callback.answer(
        f"✅ Предмет {item["name"]} успешно куплен за {item["price"]} {eco_config["currency_sign"]}",
        show_alert=True,
    )


class Duel(StatesGroup):
    choose_bet = State()


@eco_router.message(
    Command("duel"),
    CooldownFilter("duel", 3600),
    ChatTypeFilter(chat_type=["group", "supergroup"]),
)
async def cmd_duel(message: Message, bot: Bot, state: FSMContext, db: Database):
    try:
        chat_id = message.chat.id
        target_id, error = await get_user_id(message)

        if error:
            msg = await message.reply(f"❌ {error}")
            await db.reset_cooldown(message.from_user.id, "duel")
            return

        target_user = await bot.get_chat_member(chat_id, target_id)
        if target_user.user.is_bot:
            msg = await message.reply("❌ Вы пытаетесь начать дуэль с ботом")
            await db.reset_cooldown(message.from_user.id, "duel")
            return

        await state.update_data(target_id=target_id)
        msg = await message.reply(
            f"✅ Отлично!\n{eco_config["currency_sign"]} Отправьте вашу ставку или 0 для её отсутствия.\n💡 Учитывайте что деньги должны быть на руках."
        )
        await state.set_state(Duel.choose_bet)
    except Exception:
        await db.reset_cooldown(message.from_user.id, "duel")
        await error_report(message, bot, "duel", traceback.format_exc())
    finally:
        if await db.is_setting_enabled(message.chat.id, "auto_delete"):
            await asyncio.sleep(15)
            try:
                await message.delete()
                if "msg" in locals():
                    await msg.delete()
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")


@eco_router.message(Duel.choose_bet)
async def duel_choose_bet(message: Message, bot: Bot, state: FSMContext, db: Database):
    try:
        user_id = message.from_user.id
        data = await state.get_data()
        target_id = data.get("target_id")

        user_bal = await db.get_global_user_param(user_id, "money")
        target_bal = await db.get_global_user_param(target_id, "money")

        try:
            if not message.text:
                raise ValueError("Нет текста")
            bet = round(float(message.text), 2)
        except (ValueError, TypeError):
            await message.reply(
                "❌ Это не число\n💡 Отправьте число или /cancel для остановки"
            )
            return

        if bet < 0:
            await message.reply("❌ Ставка не может быть отрицательной")
            return

        if bet > 0:
            if bet > user_bal:
                await message.reply(
                    "❌ У вас не хватает денег на руках\n💡 Снимите деньги с банка с помощью /withdraw или отправьте /cancel для остановки"
                )
                return
            if bet > target_bal:
                await message.reply(
                    "❌ У цели не хватает денег на руках\n💡 Снимите деньги с банка с помощью /withdraw или отправьте /cancel для остановки"
                )
                return

        duel_id = str(uuid.uuid4())

        await state.clear()

        user_name = await db.get_global_user_param(user_id, "name")
        target_name = await db.get_global_user_param(target_id, "name")

        async with duel_sessions_lock:
            duel_sessions[duel_id] = {
                "challenger_id": user_id,
                "target_id": target_id,
                "bet": bet,
                "hp": {user_id: 150, target_id: 150},
                "turn": user_id,
                "log": [],
                "state": "wait_for_accept",
            }

        await message.reply(
            f'⚔️ <a href="tg://user?id={target_id}">{target_name}</a>, внимание!\n'
            f'🔰 <a href="tg://user?id={user_id}">{user_name}</a> вызывает вас на дуэль на {bet} {eco_config["currency_sign"]}\n\n'
            f"💡 Используйте кнопки снизу для принятия решения",
            parse_mode=ParseMode.HTML,
            reply_markup=make_duel_keyboard(duel_id),
        )
    except Exception:
        await error_report(message, bot, "duel_choose_bet", traceback.format_exc())


@eco_router.callback_query(DuelCallback.filter())
async def duel_accept_callback(
    callback: CallbackQuery, callback_data: DuelCallback, db: Database, bot: Bot
):
    try:
        duel_id = callback_data.duel_id
        user_id = callback.from_user.id

        async with duel_sessions_lock:
            duel = duel_sessions.get(duel_id)
            if duel is None:
                await callback.answer(
                    "❌ Дуэль не найдена или завершена", show_alert=True
                )
                return

            if duel["state"] != "wait_for_accept":
                await callback.answer(
                    "❌ Дуэль уже началась или завершена", show_alert=True
                )
                return

            if user_id != duel["target_id"]:
                await callback.answer(
                    "❌ Только вызванный игрок может принять или отклонить дуэль",
                    show_alert=True,
                )
                return

            if callback_data.action == "decline":
                await callback.message.edit_text("❌ Дуэль отклонена.")
                duel_sessions.pop(duel_id)
                return

            challenger_bal = await db.get_global_user_param(
                duel["challenger_id"], "money"
            )
            target_bal = await db.get_global_user_param(duel["target_id"], "money")
            bet = duel["bet"]
            if bet > challenger_bal or bet > target_bal:
                await callback.message.edit_text(
                    "❌ У одного из участников недостаточно средств для дуэли."
                )
                duel_sessions.pop(duel_id)
                return

            duel["state"] = "fight"
            await callback.message.edit_text(
                "⚔️ Дуэль началась!\n"
                f"🗡 <a href='tg://user?id={duel['challenger_id']}'>Первый ходит</a>\n"
                "Выберите действие:",
                parse_mode=ParseMode.HTML,
                reply_markup=make_duel_actions_keyboard(duel_id),
            )
    except Exception:
        await error_report(callback.message, bot, "duel_accept", traceback.format_exc())


@eco_router.callback_query(F.data.startswith("duel_action:"))
async def duel_fight_callback(callback: CallbackQuery, db: Database, bot: Bot):
    try:
        parts = callback.data.split(":")
        _, duel_id, action = parts
        user_id = callback.from_user.id

        async with duel_sessions_lock:
            duel = duel_sessions.get(duel_id)
            if duel is None:
                await callback.answer(
                    "❌ Дуэль не найдена или завершена", show_alert=True
                )
                return

            if duel["state"] != "fight":
                await callback.answer(
                    "❌ Дуэль ещё не началась или уже завершена", show_alert=True
                )
                return

            if user_id != duel["turn"]:
                await callback.answer("❌ Сейчас не ваш ход!", show_alert=True)
                return

            challenger_id = duel["challenger_id"]
            target_id = duel["target_id"]
            bet = duel["bet"]
            hp = duel["hp"]

            if "heals" not in duel:
                duel["heals"] = {challenger_id: 0, target_id: 0}
            if "failed_dodge" not in duel:
                duel["failed_dodge"] = None

            opponent_id = target_id if user_id == challenger_id else challenger_id
            msg = ""

            if duel.get("skip") == user_id:
                duel["skip"] = None
                await callback.message.edit_text(
                    f"💨 <a href='tg://user?id={user_id}'>Пропускает ход из-за лечения</a>\n\n"
                    f"❤️ {await db.get_global_user_param(challenger_id, 'name')}: {hp[challenger_id]} HP\n"
                    f"❤️ {await db.get_global_user_param(target_id, 'name')}: {hp[target_id]} HP\n\n"
                    f"💡 Теперь ходит: <a href='tg://user?id={opponent_id}'>этот игрок</a>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=make_duel_actions_keyboard(duel_id),
                )
                duel["turn"] = opponent_id
                return

            if action == "attack":
                # Критический удар
                crit = random.random() < 0.05
                dmg = random.randint(18, 28)
                if crit:
                    dmg *= 1.8
                    hp[opponent_id] -= dmg
                    msg = f"🗡 <a href='tg://user?id={user_id}'>Критический удар!</a> -{dmg} HP противнику"
                elif duel.get("dodge") == opponent_id:
                    msg = f"🗡 <a href='tg://user?id={user_id}'>Атакует!</a> Но <a href='tg://user?id={opponent_id}'>увернулся!</a> 💨"
                    duel["dodge"] = None
                elif duel.get("failed_dodge") == opponent_id:
                    dmg = int(dmg * 1.25)
                    hp[opponent_id] -= dmg
                    msg = f"🗡 <a href='tg://user?id={user_id}'>Атакует!</a> (штраф за провал уворота) -{dmg} HP противнику"
                    duel["failed_dodge"] = None
                elif random.random() < 0.1:
                    msg = f"🗡 <a href='tg://user?id={user_id}'>Промахнулся!</a>"
                else:
                    hp[opponent_id] -= dmg
                    msg = f"🗡 <a href='tg://user?id={user_id}'>Атакует!</a> -{dmg} HP противнику"
            elif action == "dodge":
                if random.random() < 0.5:
                    msg = f"🛡 <a href='tg://user?id={user_id}'>Успешно увернулся!</a>"
                    duel["dodge"] = opponent_id
                else:
                    msg = f"🛡 <a href='tg://user?id={user_id}'>Провалил уворот!</a>"
                    duel["failed_dodge"] = user_id
            elif action == "heal":
                # Ограничение на количество исцелений
                if duel["heals"][user_id] >= 2:
                    msg = f"💊 <a href='tg://user?id={user_id}'>Лечение недоступно! (макс. 2 за дуэль)</a>"
                else:
                    heal = random.randint(15, 25)
                    hp[user_id] = min(100, hp[user_id] + heal)
                    duel["heals"][user_id] += 1
                    msg = f"💊 <a href='tg://user?id={user_id}'>Лечится!</a> +{heal} HP\n⚠️ Следующий ход пропущен!"
                    duel["skip"] = user_id

            if hp[opponent_id] <= 0:
                winner_id = user_id
                loser_id = opponent_id
                winner_name = await db.get_global_user_param(winner_id, "name")

                if bet > 0:
                    await db.set_global_user_param(
                        winner_id,
                        "money",
                        (await db.get_global_user_param(winner_id, "money")) + bet,
                    )
                    await db.set_global_user_param(
                        loser_id,
                        "money",
                        (await db.get_global_user_param(loser_id, "money")) - bet,
                    )

                await callback.message.edit_text(
                    f"{msg}\n\n🏆 Победитель дуэли: <a href='tg://user?id={winner_id}'>{winner_name}</a>!\n"
                    f"💸 {'+' if bet > 0 else ''}{bet} {eco_config['currency_sign']}",
                    parse_mode=ParseMode.HTML,
                )
                duel_sessions.pop(duel_id)
                return

            duel["turn"] = opponent_id

            await callback.message.edit_text(
                f"{msg}\n\n"
                f"❤️ {await db.get_global_user_param(challenger_id, 'name')}: {hp[challenger_id]} HP\n"
                f"❤️ {await db.get_global_user_param(target_id, 'name')}: {hp[target_id]} HP\n\n"
                f"💡 Теперь ходит: <a href='tg://user?id={opponent_id}'>этот игрок</a>",
                parse_mode=ParseMode.HTML,
                reply_markup=make_duel_actions_keyboard(duel_id),
            )
    except Exception:
        await error_report(callback.message, bot, "duel_fight", traceback.format_exc())
