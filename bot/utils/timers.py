import asyncio
import copy
import datetime
import json
import os
import random
import subprocess
from pathlib import Path

import aiofiles
import aiohttp
from aiogram import Bot

from bot import BASE_DIR, FREE_GAMES_PATH, STOCKS_PATH, logger
from bot.database.database import Database
from bot.utils.ai_api import check_models
from bot.utils.bot_tools import download_osq_models
from bot.utils.get_free_epic_games import get_free_games

from .global_storage import update_cache

db = Database()

MEAN_REVERSION_STRENGTH = 0.02  # Сила возврата к базовой цене (0.01-0.05)
MOMENTUM_DECAY = 0.85  # Насколько долго держится тренд (0.7-0.95)
MAX_PRICE_MULT = 10.0  # Максимальный барьер (10х от начальной цены)
MIN_PRICE_MULT = 0.1  # Минимальный барьер (10% от начальной цены)


async def check_updates():
    while True:
        try:
            branch = (
                subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
                .decode()
                .strip()
            )
            commit = (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                .decode()
                .strip()
            )

            version_path = (
                Path(__file__).resolve().parent.parent / "config" / "version.json"
            )
            with version_path.open() as f:
                version_data = json.load(f)
                api_url = version_data.get("repo_api", None)
                if not api_url:
                    logger.error("repo_api не указан в version.json")
                    return

            api_branches_url = f"{api_url}/branches/{branch}"
            api_content_url = f"{api_url}/contents/bot/config/version.json?ref=test"

            headers = {"User-Agent": "KomaruBot/1.0"}

            async with aiohttp.ClientSession() as session:
                async with session.get(api_branches_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"📛 Ошибка API (branches), статус: {resp.status}")
                        return
                    data = await resp.json()
                    latest_commit = data["commit"]["sha"][:7]
                    update_cache["update_commit"] = latest_commit
                    update_cache["current_ver"] = version_data.get(branch, "unknown")
                    update_cache["has_update"] = latest_commit != commit

                headers["Accept"] = "application/vnd.github.v3.raw"
                async with session.get(api_content_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"📛 Ошибка API (version.json), статус: {resp.status}"
                        )
                        return
                    text = await resp.text()
                    data = json.loads(text)
                    update_cache["latest_ver"] = data.get(branch, "unknown")

            update_cache["current_commit"] = commit
            update_cache["branch"] = branch

            if update_cache["has_update"]:
                logger.info(f"⚡️ Доступно обновление: {commit} -> {latest_commit}")
            else:
                logger.info("☃️ Обновлений нет")

        except Exception as e:
            logger.exception(f"📛 Ошибка при проверке обновлений: {e}")
        await asyncio.sleep(1200)


async def cleanup_expired_items_task():
    """Задача для ежедневной очистки истёкших предметов"""
    while True:
        await db.cleanup_all_expired_items()
        await asyncio.sleep(86400)  # Интервал 24 часа (86400 секунд)


async def check_free_games(bot: Bot):
    logger.info("🔄 Служба обновления игр запущена.")

    clean_run = not FREE_GAMES_PATH.exists()

    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            target_weekday = 3  # Четверг
            target_hour = 15  # 15:00 UTC

            # Вычисляем ближайший четверг 15:00 UTC
            days_ahead = (target_weekday - now_utc.weekday() + 7) % 7
            next_run = (now_utc + datetime.timedelta(days=days_ahead)).replace(
                hour=target_hour, minute=0, second=0, microsecond=0
            )

            # Если уже прошёл — берём следующий четверг
            if next_run <= now_utc:
                next_run += datetime.timedelta(days=7)

            if not clean_run:
                sleep_seconds = (next_run - now_utc).total_seconds()
                logger.info(
                    f"Следующее обновление: {next_run.isoformat()}. 🔄 Сон на {sleep_seconds:.0f} секунд."
                )
                await asyncio.sleep(sleep_seconds)
            else:
                logger.info(
                    "🔄 Файл не найден — выполняем немедленное первое обновление."
                )
                clean_run = False

            # Обновление данных
            logger.info("🔄 Начинаем обновление бесплатных игр.")
            games_available, games_unavailable = await get_free_games()

            games_to_save = {
                "available": games_available,
                "unavailable": games_unavailable,
                "_updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }

            FREE_GAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = FREE_GAMES_PATH.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(games_to_save, f, indent=2, ensure_ascii=False)
            tmp_path.replace(FREE_GAMES_PATH)

            logger.info(
                "⌛️ Бесплатные игры успешно обновлены, запускаем рассылку в чаты."
            )
            msg_lines = []

            if games_to_save["available"]:
                msg_lines.append("🎁 <b>Бесплатно сейчас:</b>\n")
                for game in games_to_save["available"].values():
                    start = datetime.datetime.fromisoformat(game["start"]).strftime(
                        "%d.%m %H:%M"
                    )
                    end = datetime.datetime.fromisoformat(game["end"]).strftime(
                        "%d.%m %H:%M"
                    )
                    msg_lines.append(
                        f"🎮 <b>{game['title']}</b>\n"
                        f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                        f"🗓️ <i>{start} UTC — {end} UTC</i>\n"
                        f"🆔 <code>{game['slug']}</code>\n"
                    )

            if games_to_save["unavailable"]:
                msg_lines.append("\n🔒 <b>Не доступно в РФ:</b>\n")
                for game in games_to_save["unavailable"].values():
                    start = datetime.datetime.fromisoformat(game["start"]).strftime(
                        "%d.%m %H:%M"
                    )
                    end = datetime.datetime.fromisoformat(game["end"]).strftime(
                        "%d.%m %H:%M"
                    )
                    msg_lines.append(
                        f"🎮 <b>{game['title']}</b>\n"
                        f"🔗 <a href=\"{game['url']}\">Ссылка на игру</a>\n"
                        f"🗓️ <i>{start} UTC — {end} UTC</i>\n"
                        f"🆔 <code>{game['slug']}</code>\n"
                    )

            if games_to_save["_updated_at"]:
                dt = datetime.datetime.fromisoformat(games_to_save["_updated_at"])
                msg_lines.append(f"\n⌛️ Обновлено: {dt.strftime('%d.%m %H:%M UTC')}")

            message_text = "\n".join(msg_lines)

            for chat_id in await db.get_chats_with_setting("auto_eg_free"):
                try:
                    await bot.send_message(
                        chat_id,
                        message_text,
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.warning(
                        f"⚠️ Не удалось отправить сообщение в чат {chat_id}: {e}"
                    )

        except asyncio.CancelledError:
            logger.info("🛑 Задача обновления игр отменена.")
            break
        except Exception as e:
            logger.exception(
                f"📛 Произошла ошибка при обновлении игр: {e}\n▶️ Повторная попытка через 10 минут..."
            )
            await asyncio.sleep(600)


async def change_stocks():
    while True:
        try:
            basic_stocks_path = BASE_DIR / "config" / "basic_stocks.json"

            async with aiofiles.open(basic_stocks_path, "r", encoding="utf-8") as file:
                basic_data = json.loads(await file.read())

            current_data = {}
            if os.path.exists(STOCKS_PATH):
                async with aiofiles.open(STOCKS_PATH, "r", encoding="utf-8") as file:
                    current_data = json.loads(await file.read())
            else:
                for key, data in basic_data.items():
                    current_data[key] = copy.deepcopy(data)
                    current_data[key]["momentum"] = 0.0
                    current_data[key]["history"] = [data["price"]]

            active_keys = set(basic_data.keys())
            current_data = {k: v for k, v in current_data.items() if k in active_keys}

            for key in active_keys:
                if key not in current_data:
                    current_data[key] = copy.deepcopy(basic_data[key])
                    current_data[key]["momentum"] = 0.0
                    current_data[key].setdefault("history", [basic_data[key]["price"]])

                stock = current_data[key]
                base_price = basic_data[key]["price"]
                current_price = stock["price"]
                vol = stock["volatility"]

                # Momentum
                if random.random() < 0.15:
                    stock["momentum"] = random.uniform(-vol, vol)
                else:
                    stock["momentum"] *= MOMENTUM_DECAY

                # Mean reversion
                deviation = (base_price - current_price) / base_price
                reversion = deviation * MEAN_REVERSION_STRENGTH

                # GBM
                noise = random.normalvariate(0, vol)
                change_percent = reversion + stock["momentum"] + noise

                new_price = current_price * (1 + change_percent)
                new_price = max(
                    min(new_price, base_price * MAX_PRICE_MULT),
                    base_price * MIN_PRICE_MULT,
                )
                stock["price"] = round(new_price, 2)

                history = stock.get("history", [])
                history.append(stock["price"])
                stock["history"] = history[-10:]

            async with aiofiles.open(STOCKS_PATH, "w", encoding="utf-8") as file:
                await file.write(json.dumps(current_data, ensure_ascii=False, indent=2))

            leader = max(
                current_data.values(),
                key=lambda x: (
                    x["price"]
                    - basic_data[next(k for k, v in current_data.items() if v == x)][
                        "price"
                    ]
                ),
            )
            logger.info(
                f"📈 Рынок обновлен. В лидерах: {leader['name']} ({leader['price']}🪙)"
            )

        except Exception as e:
            logger.critical(f"❌ Критическая ошибка рынка: {e}", exc_info=True)

        await asyncio.sleep(1800)


async def update_osq_models():
    while True:
        try:
            await asyncio.sleep(86400)
            await download_osq_models()
        except Exception as e:
            logger.critical(
                f"❌ Не удалось обновить ИИ модели с OnlySq: {e}", exc_info=True
            )


async def check_models_timer():
    while True:
        await asyncio.sleep(14400)
        try:
            await check_models(include_image=True, force_refresh=True)
        except Exception as e:
            logger.critical(
                f"❌ Не удалось обновить ИИ модели с OnlySq: {e}", exc_info=True
            )


async def background_checker(bot: Bot):
    """Главная функция для запуска фоновых задач"""
    update_task = asyncio.create_task(check_updates())
    cleanup_task = asyncio.create_task(cleanup_expired_items_task())
    epic_task = asyncio.create_task(check_free_games(bot))
    update_stocks = asyncio.create_task(change_stocks())
    update_osq = asyncio.create_task(update_osq_models())
    check_models = asyncio.create_task(check_models_timer())

    # Ждём того чего не случится
    await asyncio.gather(
        update_task, cleanup_task, epic_task, update_stocks, update_osq, check_models
    )
