import math
import time

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from bot import logger
from bot.database.database import Database
from bot.filters.chat_type import ChatTypeFilter
from bot.filters.cooldown_filter import CooldownFilter
from bot.keyboards.callback_data import PremiumBuyCallback
from bot.keyboards.premium_keyboard import make_premium_kb

premium_router = Router()

# Расценки
PREMIUM_PRICE_STARS = 99
PREMIUM_DAYS = 30

# Преимущества
PREMIUM_FEATURES = (
    "✨ Доступ к премиум-моделям ИИ\n"
    "⏳ Уменьшенные кулдауны (кроме экономики)\n"
    "🎁 Эксклюзивные функции в будущем"
)


async def send_premium_invoice(bot: Bot, chat_id: int, user_id: int, days: int) -> bool:
    """Вспомогательная функция для генерации и отправки инвойса Telegram Stars."""
    prices = [LabeledPrice(label=f"Премиум на {days} дней", amount=PREMIUM_PRICE_STARS)]
    payload = f"premium:{user_id}:{days}:{int(time.time())}"

    try:
        await bot.send_invoice(
            chat_id=chat_id,
            title="Премиум подписка",
            description=f"Активация премиум-статуса на {days} дней. Получите доступ к продвинутым ИИ-моделям и прочим функциям!",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="premium_buy",
        )
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке инвойса для пользователя {user_id}: {e}")
        return False


@premium_router.message(
    Command("premium"), CooldownFilter("premium", 30), ChatTypeFilter("private")
)
async def cmd_premium(message: Message, db: Database):
    if not message.from_user:
        return

    user_id = message.from_user.id
    is_premium = await db.is_premium_user(user_id)

    if is_premium:
        expire_ts = await db.get_premium_expire(user_id)
        now = int(time.time())
        if expire_ts and expire_ts > now:
            remaining_days = math.ceil((expire_ts - now) / (24 * 60 * 60))
        else:
            remaining_days = 0

        status_text = (
            f"✨ У вас активирован премиум-статус! Осталось {remaining_days} дней."
        )
    else:
        status_text = "❌ У вас нет премиум-статуса."
    action_text = (
        "" if is_premium else "\n\nВы можете приобрести его, нажав на кнопку ниже:"
    )

    text = (
        f"{status_text}\n\n"
        f"<b>Премиум-статус дает следующие преимущества:</b>\n"
        f"{PREMIUM_FEATURES}"
        f"{action_text}"
    )

    await message.reply(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=make_premium_kb(user_id, is_premium),
    )


@premium_router.callback_query(PremiumBuyCallback.filter())
async def process_premium_callback(
    query: CallbackQuery, callback_data: PremiumBuyCallback, bot: Bot, db: Database
):
    user_id = callback_data.user_id
    action = callback_data.action
    time_days = callback_data.time or PREMIUM_DAYS

    await query.answer()
    if not query.message:
        return

    if action == "info":
        info_text = (
            "📌 <b>Что такое Премиум?</b>\n\n"
            f"<b>Премиум-подписка дает вам:</b>\n{PREMIUM_FEATURES}\n\n"
            f"💰 Стоимость: {PREMIUM_PRICE_STARS} ⭐ (Telegram Stars)\n"
            f"📅 Длительность: {time_days} дней"
        )
        is_premium = await db.is_premium_user(user_id)
        await query.message.edit_text(  # pyright: ignore[reportAttributeAccessIssue]
            info_text,
            parse_mode=ParseMode.HTML,
            reply_markup=make_premium_kb(user_id, is_premium),
        )
        return

    if action in ("buy", "extend"):
        success = await send_premium_invoice(
            bot, query.message.chat.id, user_id, time_days
        )
        if not success:
            await query.message.answer(
                "❌ Ошибка при инициировании платежа. Попробуйте позже."
            )


@premium_router.message(Command("buy_premium"), ChatTypeFilter("private"))
async def cmd_buy_premium(message: Message, bot: Bot):
    if not message.from_user:
        return

    success = await send_premium_invoice(
        bot, message.chat.id, message.from_user.id, PREMIUM_DAYS
    )
    if not success:
        await message.answer("❌ Ошибка при инициировании платежа. Попробуйте позже.")


@premium_router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    if pre_checkout_query.invoice_payload.startswith("premium:"):
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id, ok=True
        )
    else:
        await bot.answer_pre_checkout_query(
            pre_checkout_query_id=pre_checkout_query.id,
            ok=False,
            error_message="❌ Произошла ошибка. Неверный формат платежа.",
        )


@premium_router.message(F.successful_payment)
async def handle_successful_payment(message: Message, db: Database):
    """Обрабатывает успешный платеж и начисляет премиум."""
    payment = message.successful_payment
    if not payment or not payment.invoice_payload.startswith("premium:"):
        return

    payload = payment.invoice_payload

    try:
        _, payload_user_id, payload_days, _ = payload.split(":")
        days = int(payload_days)
        user_id = int(payload_user_id)

        # Получим, сколько дней было до пополнения
        prev_expire = await db.get_premium_expire(user_id)
        now = int(time.time())
        if prev_expire and prev_expire > now:
            prev_days = math.ceil((prev_expire - now) / (24 * 60 * 60))
        else:
            prev_days = 0

        # Добавим дни и получим новый timestamp окончания
        new_expire = await db.add_premium_days(user_id, days)
        if new_expire and new_expire > now:
            new_days = math.ceil((new_expire - now) / (24 * 60 * 60))
        else:
            new_days = 0

        await message.answer(
            f"✅ <b>Спасибо за покупку!</b>\n\n"
            f"🎉 Премиум обновлён: было <b>{prev_days} дней</b>, стало <b>{new_days} дней</b> (+{days} дней).\n\n"
            f"<b>Ваши преимущества:</b>\n{PREMIUM_FEATURES}",
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            f"✅ Премиум начислен пользователю {user_id} (+{days} дней). Было {prev_days}, стало {new_days}. Сумма: {payment.total_amount} Stars"
        )

    except (ValueError, IndexError) as e:
        logger.error(
            f"❌ Критическая ошибка парсинга payload '{payload}': {e}", exc_info=True
        )
        await message.answer(
            "❌ Произошла ошибка при автоматической активации премиума. Пожалуйста, напишите в поддержку.",
            parse_mode=ParseMode.HTML,
        )
