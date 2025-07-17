import asyncio
import datetime
import json
import subprocess
from pathlib import Path

import aiohttp

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


async def check_free_games():
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        weekday = now.weekday()  # четверг = 3
        hour = now.hour
        minute = now.minute

        if weekday == 3 and 14 <= hour <= 16:
            if hour == 15 and 0 <= minute < 30:
                # Проверка на то, что уже обновляли сегодня
                if FREE_GAMES_PATH.exists():
                    try:
                        with FREE_GAMES_PATH.open(encoding="utf-8") as f:
                            data = json.load(f)
                            cached_ts = data.get("_updated_at")
                            if cached_ts:
                                updated_dt = datetime.datetime.fromisoformat(cached_ts)
                                if updated_dt.date() == now.date():
                                    logger.debug(
                                        "Игры уже обновлены сегодня, пропускаем."
                                    )
                                    await asyncio.sleep(86400)
                                    continue
                    except Exception as e:
                        logger.warning(f"Не удалось прочитать кэш: {e}")

                try:
                    games_data = await get_free_games()
                    games_data = {
                        "available": games_data[0],
                        "unavailable": games_data[1],
                        "_updated_at": now.isoformat(),
                    }

                    FREE_GAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with FREE_GAMES_PATH.open("w", encoding="utf-8") as f:
                        json.dump(games_data, f, indent=2, ensure_ascii=False)

                    logger.info(f"Бесплатные игры обновлены ({now.isoformat()})")
                    await asyncio.sleep(86400)
                    continue

                except Exception as e:
                    logger.exception(f"Ошибка при обновлении бесплатных игр: {e}")
                    await asyncio.sleep(600)
                    continue

            await asyncio.sleep(300)
        else:
            await asyncio.sleep(3600)


async def background_checker():
    """Главная функция для запуска фоновых задач"""
    update_task = asyncio.create_task(check_updates_task())
    cleanup_task = asyncio.create_task(cleanup_expired_items_task())
    epic_task = asyncio.create_task(check_free_games())

    # Ждём того чего не случится
    await asyncio.gather(update_task, cleanup_task, epic_task)
