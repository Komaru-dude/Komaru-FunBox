import asyncio
import datetime
import json
import subprocess
from pathlib import Path

import aiohttp
from aiogram import Bot

from bot import logger
from bot.database import Database
from bot.utils.get_free_epic_games import get_free_games

from .global_storage import FREE_GAMES_PATH, update_cache

db = Database()


async def check_updates():
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

        version_path = Path(__file__).resolve().parent.parent / "version.json"
        with version_path.open() as f:
            version_data = json.load(f)
            api_url = version_data.get("repo_api", None)
            if not api_url:
                logger.error("repo_api не указан в version.json")
                return

        api_branches_url = f"{api_url}/branches/{branch}"
        api_content_url = f"{api_url}/contents/bot/version.json?ref=test"

        headers = {"User-Agent": "KomaruBot/1.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(api_branches_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка API (branches), статус: {resp.status}")
                    return
                data = await resp.json()
                latest_commit = data["commit"]["sha"][:7]
                update_cache["update_commit"] = latest_commit
                update_cache["current_ver"] = version_data.get(branch, "unknown")
                update_cache["has_update"] = latest_commit != commit

            headers["Accept"] = "application/vnd.github.v3.raw"
            async with session.get(api_content_url, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка API (version.json), статус: {resp.status}")
                    return
                text = await resp.text()
                data = json.loads(text)
                update_cache["latest_ver"] = data.get(branch, "unknown")

        update_cache["current_commit"] = commit
        update_cache["branch"] = branch

        if update_cache["has_update"]:
            logger.info(f"Доступно обновление: {commit} -> {latest_commit}")
        else:
            logger.info("Обновлений нет")

    except Exception as e:
        logger.exception(f"Ошибка при проверке обновлений: {e}")


async def check_updates_task():
    """Задача для периодической проверки обновлений"""
    while True:
        await check_updates()
        await asyncio.sleep(1200)  # Интервал 20 минут


async def cleanup_expired_items_task():
    """Задача для ежедневной очистки истёкших предметов"""
    while True:
        await db.cleanup_all_expired_items()
        await asyncio.sleep(86400)  # Интервал 24 часа (86400 секунд)


async def check_free_games(bot: Bot):
    logger.info("Служба обновления игр запущена.")

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
                    f"Следующее обновление: {next_run.isoformat()}. Сон на {sleep_seconds:.0f} секунд."
                )
                await asyncio.sleep(sleep_seconds)
            else:
                logger.info("Файл не найден — выполняем немедленное первое обновление.")
                clean_run = False

            # Обновление данных
            logger.info("Начинаем обновление бесплатных игр.")
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

            logger.info("Бесплатные игры успешно обновлены, запускаем рассылку в чаты.")
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
                        f"Не удалось отправить сообщение в чат {chat_id}: {e}"
                    )

        except asyncio.CancelledError:
            logger.info("Задача обновления игр отменена.")
            break
        except Exception as e:
            logger.exception(
                f"Произошла ошибка при обновлении игр: {e}\nПовторная попытка через 10 минут..."
            )
            await asyncio.sleep(600)


async def background_checker(bot: Bot):
    """Главная функция для запуска фоновых задач"""
    update_task = asyncio.create_task(check_updates_task())
    cleanup_task = asyncio.create_task(cleanup_expired_items_task())
    epic_task = asyncio.create_task(check_free_games(bot))

    # Ждём того чего не случится
    await asyncio.gather(update_task, cleanup_task, epic_task)
