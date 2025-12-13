import asyncio
import json

import aiohttp

from bot import DATA_DIR, logger
from bot.utils.global_storage import onlysq_models

models_path = DATA_DIR / "models.json"
default_models = {"models": {}}


async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"API Error: Status {response.status}")
            return await response.json()


async def make_post_request(url, payload, headers=None):
    async with aiohttp.ClientSession() as session:
        request_kwargs = {"json": payload}
        if headers is not None:
            request_kwargs["headers"] = headers

        async with session.post(url, **request_kwargs) as response:
            if response.status != 200 or not response.content:
                return None, f"❌ Ошибка API: статус {response.status}"
            try:
                return await response.json(), None
            except Exception as e:
                return None, f"❌ Ошибка обработки ответа: {str(e)}"


async def download_osq_models():
    try:
        models = await fetch_json("https://api.onlysq.ru/ai/models")

        if not isinstance(models, dict) or not isinstance(models.get("models"), dict):
            raise ValueError("❌ API вернул некорректный формат моделей")

        with open(models_path, "w") as f:
            json.dump(models, f, indent=2)

        onlysq_models.clear()
        onlysq_models.update(models)
        logger.info(f"✅ Успешно загружено {len(models['models'])} моделей")
        return

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки с API: {e}")
        onlysq_models.update(default_models)
        return
