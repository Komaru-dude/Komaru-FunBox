import json
import os

import aiohttp

from bot import DATA_DIR, logger
from bot.utils.global_storage import onlysq_models

models_path = DATA_DIR / "models.json"
default_models = {"models": {}}

MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")
MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"


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


async def fetch_marketaux_news(limit: int = 20) -> list[str]:
    if not MARKETAUX_API_KEY:
        logger.warning("⚠️ MARKETAUX_API_KEY не задан - новости не будут получены")
        return []

    params = {
        "api_token": MARKETAUX_API_KEY,
        "language": "en",
        "limit": limit,
        "sort": "published_desc",
        "filter_entities": "true",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(MARKETAUX_URL, params=params, timeout=15) as resp:
                if resp.status != 200:
                    logger.warning(f"⚠️ Marketaux вернул {resp.status}")
                    return []
                data = await resp.json()
    except Exception as e:
        logger.warning(f"⚠️ Ошибка получения новостей marketaux: {e}")
        return []

    items = data.get("data", []) or []
    headlines: list[str] = []
    for it in items:
        title = (it.get("title") or "").strip()
        desc = (it.get("description") or "").strip()
        entities = it.get("entities") or []
        industries = {
            ent.get("industry")
            for ent in entities
            if ent.get("industry") and ent.get("industry") != "N/A"
        }

        if not title:
            continue

        content_block = f"Title: {title}"
        if desc:
            content_block += f"\nDescription: {desc}"
        if industries:
            content_block += f"\nRelated Industries: {', '.join(industries)}"

        headlines.append(content_block)
    return headlines
