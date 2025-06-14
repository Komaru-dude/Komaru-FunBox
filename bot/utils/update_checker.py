import aiohttp
import asyncio
import json
import logging
import subprocess
from .global_storage import update_cache
from pathlib import Path


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
                logging.error("repo_api не указан в version.json")
                return

        api_branches_url = f"{api_url}/branches/{branch}"
        api_content_url = f"{api_url}/contents/bot/version.json?ref=test"

        headers = {"User-Agent": "KomaruBot/1.0"}

        async with aiohttp.ClientSession() as session:
            async with session.get(api_branches_url, headers=headers) as resp:
                if resp.status != 200:
                    logging.error(f"Ошибка API (branches), статус: {resp.status}")
                    return
                data = await resp.json()
                latest_commit = data["commit"]["sha"][:7]
                update_cache["update_commit"] = latest_commit
                update_cache["current_ver"] = version_data.get(branch, "unknown")
                update_cache["has_update"] = latest_commit != commit

            headers["Accept"] = "application/vnd.github.v3.raw"
            async with session.get(api_content_url, headers=headers) as resp:
                if resp.status != 200:
                    logging.error(f"Ошибка API (version.json), статус: {resp.status}")
                    return
                text = await resp.text()
                data = await json.loads(text)
                update_cache["latest_ver"] = data.get(branch, "unknown")

        update_cache["current_commit"] = commit
        update_cache["branch"] = branch

        if update_cache["has_update"]:
            logging.info(f"Доступно обновление: {commit} -> {latest_commit}")
        else:
            logging.info("Обновлений нет")

    except Exception as e:
        logging.exception(f"Ошибка при проверке обновлений: {e}")


async def background_update_checker():
    while True:
        await check_updates()
        await asyncio.sleep(1200)  # 20 минут
