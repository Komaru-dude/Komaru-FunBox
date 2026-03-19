import base64
import json
import os
import time
from typing import Any, AsyncGenerator, Optional

import aiohttp
import magic
import openai

from bot import logger
from bot.database.redis_client import redis_db
from bot.utils.global_storage import filtered_models, onlysq_models

client = openai.AsyncOpenAI(
    api_key=os.getenv("ONLYSQ_API_KEY"),
    base_url=os.getenv("OPENAI_SDK_API_URL"),
)

JIGSAW_API_KEY = os.getenv("JIGSAW_API_KEY")

ALLOWED_RATIOS = {
    "1:1",
    "16:9",
    "21:9",
    "3:2",
    "2:3",
    "4:5",
    "5:4",
    "3:2",
    "2:3",
    "4:5",
    "5:4",
    "3:4",
    "4:3",
    "9:16",
    "9:21",
}


class LocalRateLimitError(Exception):
    """Выбрасывается, когда наш API вываливается в рейтлимит"""

    def __init__(self, message: str):
        super().__init__(message)


async def generate_image_api(model: str, prompt: str, ratio: str = "1:1") -> dict:
    """Генерация изображений через внешний API."""
    if not await check_rpm_limit(model):
        return {
            "error": True,
            "status": 429,
            "msg": "Превышен лимит RPM для данной модели. Попробуйте позже или выберите другую модель.",
        }

    if ratio not in ALLOWED_RATIOS:
        return {"error": True, "msg": f"Недопустимое соотношение сторон: {ratio}"}

    request_data = {"model": model, "prompt": prompt, "ratio": ratio}
    headers = {"Authorization": f"Bearer {os.getenv('ONLYSQ_API_KEY')}"}
    img_url = os.getenv("IMAGEN_API_URL")

    if not img_url:
        return {"error": True, "msg": "IMAGEN_API_URL не настроен в env."}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                img_url, json=request_data, headers=headers
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    return {"error": True, "status": resp.status, "msg": data}
                return {
                    "error": False,
                    "file": base64.b64decode(data["files"][0]),
                    "elapsed_time": data.get("elapsed-time", 0),
                }
    except Exception as e:
        return {"error": True, "msg": str(e)}


async def stream_text_api(
    model: str,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: str = "auto",
) -> AsyncGenerator[str, None]:
    if not await check_rpm_limit(model):
        raise LocalRateLimitError(
            "Превышен лимит RPM для данной модели. Попробуйте позже или выберите другую модель."
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    if tools is not None:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    stream = await client.chat.completions.create(**kwargs)

    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def simple_text_api(model: str, messages: list) -> str:
    """Обычный запрос текста (без стриминга)."""
    if not await check_rpm_limit(model):
        raise LocalRateLimitError(
            "Превышен лимит RPM для данной модели. Попробуйте позже или выберите другую модель."
        )

    response = await client.chat.completions.create(
        model=model, messages=messages, stream=False
    )
    if not response.choices:
        return ""
    return response.choices[0].message.content  # type: ignore


async def ocr_process_api(file_bytes: bytes, file_ext: str = "jpg") -> str:
    """Распознавание текста через JigsawStack."""
    if not JIGSAW_API_KEY:
        raise ValueError("JIGSAW_API_KEY не найден в переменных окружения.")

    url = "https://api.jigsawstack.com/v1/vocr"

    form = aiohttp.FormData()

    content_type = f"image/{'jpeg' if file_ext.lower() == 'jpg' else file_ext.lower()}"
    form.add_field(
        name="file",
        value=file_bytes,
        filename=f"image.{file_ext}",
        content_type=content_type,
    )

    payload = {
        "prompt": "Extract all visible text from the image exactly as it appears, line by line."
    }
    form.add_field(
        name="body",
        value=json.dumps(payload),
        content_type="application/json",
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            data=form,
            headers={"x-api-key": JIGSAW_API_KEY},
        ) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise RuntimeError(f"Ошибка OCR: {resp.status} — {error_text}")

            res = await resp.json()

            if "sections" not in res:
                return f"Ошибка OCR: {res}"

            return "\n".join(s.get("text", "") for s in res.get("sections", []))


async def check_models(
    tier_filtered: bool = True, include_image: bool = False, force_refresh: bool = False
):
    """Асинхронная проверка доступности моделей."""
    cache_key = "check_models_cache"

    if not force_refresh:
        try:
            cached_result = await redis_db.client.get(cache_key)
            if cached_result:
                logger.info("💾 Загружаем модели из кэша")
                checked_models = json.loads(cached_result)
                filtered_models.clear()
                filtered_models.update(checked_models)
                logger.info(
                    f"✅ Модели загружены из кэша, рабочие: {len(checked_models)}"
                )
                return
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при чтении кэша: {e}")

    logger.info("🧠 Проверяем доступность моделей")

    free_models = [
        m.strip()
        for m in os.getenv("ONLYSQ_ALLOWED_FREE_MODELS", "").split(",")
        if m.strip()
    ]
    premium_models = [
        m.strip()
        for m in os.getenv("ONLYSQ_ALLOWED_PREMIUM_MODELS", "").split(",")
        if m.strip()
    ]
    allowed_ids = set(free_models + premium_models)

    all_api_models = onlysq_models.get("models", {})
    checked_models = {}
    current_tier = int(os.getenv("ONLYSQ_TIER", 0))

    test_messages = [
        {"role": "user", "content": "Write hello world"},
    ]

    for model_id in allowed_ids:
        if model_id not in all_api_models:
            logger.error(
                f"❌ Модель {model_id} указана в .env, но отсутствует в API OnlySQ!"
            )
            continue

        model = all_api_models[model_id]

        if tier_filtered and model.get("tier", 0) > current_tier:
            logger.info(f"⏭ Пропускаем {model_id}: ваш Tier ниже необходимого.")
            continue

        logger.info(f"⌛️ Проверяем модель {model["name"]}")

        if tier_filtered and model["tier"] > current_tier:
            continue

        if model["modality"] == "text":
            try:
                model_answer = await simple_text_api(model_id, test_messages)

                if not len(model_answer) > 5:
                    raise RuntimeError

                checked_models[model_id] = model
            except Exception as e:
                logger.warning(f"⚠️ Модель {model["name"]} не ответила. Ошибка: {e}")
        elif model["modality"] == "image" and include_image:
            try:
                api_resp = await generate_image_api(model_id, "Ginger cat")

                if api_resp.get("error"):
                    raise RuntimeError(f"API вернуло ошибку: {api_resp.get("error")}")

                image_bytes = api_resp.get("file")

                if not image_bytes or not isinstance(image_bytes, bytes):
                    raise RuntimeError("Поле 'file' пустое или имеет неверный формат")

                mime = magic.from_buffer(image_bytes, mime=True)

                if not mime.startswith("image/"):
                    raise RuntimeError("Модель не вернула изображение")

                checked_models[model_id] = model
            except Exception as e:
                logger.warning(f"⚠️ Модель {model["name"]} не ответила. Ошибка: {e}")

    filtered_models.clear()
    filtered_models.update(checked_models)

    try:
        cache_data = json.dumps(checked_models)
        await redis_db.client.set(cache_key, cache_data)
        logger.info("💾 Результаты сохранены в кэш")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при сохранении в кэш: {e}")

    logger.info(f"✅ Модели проверены, рабочие: {len(checked_models)}")


async def check_rpm_limit(model_id: str) -> bool:
    """
    Проверяет RPM лимит на основе ONLYSQ_TIER сервера.
    Возвращает True, если слот есть.
    Если лимит превышен (с учетом 1 прозапас), возвращает False.

    Args:
        model_id: ID модели
    """
    server_tier = int(os.getenv("ONLYSQ_TIER", 0))
    model_info = onlysq_models.get("models", {}).get(model_id)

    if not model_info or "limits" not in model_info:
        return True

    limit = max(0, model_info["limits"][server_tier] - 1)

    now = time.time()
    current_minute = int(now // 60)
    key = f"rpm_limit:{model_id}:{current_minute}"

    current_usage = await redis_db.client.incr(key)
    if current_usage == 1:
        await redis_db.client.expire(key, 60)

    if current_usage > limit:
        return False

    return True
