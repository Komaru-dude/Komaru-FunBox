import asyncio
import base64
import json
import os
import re
import time
from typing import Any, AsyncGenerator, Optional

import aiohttp
import litellm
import magic

from bot import logger
from bot.database.redis_client import redis_db
from bot.utils.ai.providers import (
    fallback_max_chain,
    get_all_models,
    healthcheck_cooldowns,
    healthcheck_enabled,
    model_route_alternates,
    provider_credentials,
    resolve_model,
)
from bot.utils.global_storage import filtered_models

litellm.drop_params = True
try:
    litellm.suppress_debug_info = True
except Exception:
    pass

JIGSAW_API_KEY = os.getenv("JIGSAW_API_KEY")

_MODEL_HEALTH_CACHE_KEY = "check_models_health_v2"
_MODEL_LIST_CACHE_KEY = "check_models_cache"
_model_health: dict[str, dict[str, Any]] = {}
_model_health_loaded = False
_model_health_lock = asyncio.Lock()

ALLOWED_RATIOS = {
    "1:1",
    "16:9",
    "21:9",
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
    """Выбрасывается, когда мы уперлись в локальные лимиты пользователя или сервера"""

    def __init__(self, message: str):
        super().__init__(message)


def _is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, LocalRateLimitError):
        return True

    exc_str = str(exc).lower()
    if "rate limit" in exc_str or "429" in exc_str:
        return True

    return False


async def _load_model_health() -> None:
    global _model_health_loaded
    if _model_health_loaded:
        return
    try:
        raw = await redis_db.client.get(_MODEL_HEALTH_CACHE_KEY)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                _model_health.update(data)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка чтения healthcheck-кэша: {e}")
    _model_health_loaded = True


async def _save_model_health() -> None:
    try:
        await redis_db.client.set(
            _MODEL_HEALTH_CACHE_KEY,
            json.dumps(_model_health, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"⚠️ Ошибка сохранения healthcheck-кэша: {e}")


def _mark_model_failed(model_id: str, reason: BaseException) -> None:
    _model_health[model_id] = {
        "available": False,
        "checked_at": time.time(),
        "error": f"{type(reason).__name__}: {reason}",
    }
    filtered_models.pop(model_id, None)
    logger.warning(
        f"🚫 Модель {model_id} на cooldown после ошибки: "
        f"{type(reason).__name__}: {reason}"
    )
    try:
        asyncio.get_running_loop().create_task(_save_model_health())
    except RuntimeError:
        pass


def _mark_model_succeeded(model_id: str) -> None:
    previous = _model_health.get(model_id)
    _model_health[model_id] = {
        "available": True,
        "checked_at": time.time(),
        "error": None,
    }

    model = get_all_models().get(model_id)
    if model and not model.get("hidden"):
        filtered_models[model_id] = model

    if previous and not previous.get("available", True):
        logger.info(f"✅ Модель {model_id} снова доступна")

    try:
        asyncio.get_running_loop().create_task(_save_model_health())
    except RuntimeError:
        pass


def _model_is_cooling_down(model_id: str) -> bool:
    state = _model_health.get(model_id)
    if not state or state.get("available", True):
        return False
    _, failure_cooldown = healthcheck_cooldowns(model_id)
    return time.time() - float(state.get("checked_at", 0)) < failure_cooldown


def _auto_fallbacks(primary: str, user_tier: int, max_chain: int) -> list[str]:
    """Подбор резервных моделей той же модальности из нового списка"""
    if max_chain <= 0:
        return []

    all_models = get_all_models()
    primary_info = filtered_models.get(primary) or all_models.get(primary, {})
    modality = primary_info.get("modality", "text")

    result: list[str] = []
    for mid, m in all_models.items():
        if mid == primary:
            continue
        if m.get("hidden"):
            continue
        if m.get("modality") != modality:
            continue
        if m.get("is_premium") and user_tier <= 0:
            continue

        result.append(mid)
        if len(result) >= max_chain:
            break

    return result


def _route_alternates(primary: str, user_tier: int) -> list[str]:
    """Та же модель через других провайдеров — пробуются раньше фолбэков."""
    all_models = get_all_models()
    result: list[str] = []
    for mid in model_route_alternates(primary):
        if all_models.get(mid, {}).get("is_premium") and user_tier <= 0:
            continue
        result.append(mid)
    return result


def _build_candidates(
    primary: str, fallbacks: list[str] | None, user_tier: int
) -> list[str]:
    if fallbacks is None:
        chain = _auto_fallbacks(primary, user_tier, fallback_max_chain(user_tier))
    else:
        chain = list(fallbacks)

    routes = _route_alternates(primary, user_tier)

    seen: set[str] = set()
    ordered: list[str] = []
    for mid in [primary, *routes, *chain]:
        if mid and mid not in seen and not _model_is_cooling_down(mid):
            seen.add(mid)
            ordered.append(mid)
    return ordered


def _ratio_to_size(ratio: str) -> str:
    """Соотношение сторон -> размер ~1МП, кратный 64 (формат OpenAI Images '1024x1024')."""
    w_ratio, h_ratio = (int(x) for x in ratio.split(":"))
    scale = (1024 * 1024 / (w_ratio * h_ratio)) ** 0.5

    def _to64(value: float) -> int:
        return max(256, round(value / 64) * 64)

    return f"{_to64(w_ratio * scale)}x{_to64(h_ratio * scale)}"


async def generate_image_api(model: str, prompt: str, ratio: str = "1:1") -> dict:
    """Генерация изображения через litellm. Без фолбэков на другие модели:
    функцию использует healthcheck, которому нужен ответ именно этой модели."""
    if not await check_rpm_limit(model):
        return {
            "error": True,
            "status": 429,
            "msg": "Превышен лимит для данной модели.",
        }

    if ratio not in ALLOWED_RATIOS:
        return {"error": True, "msg": f"Недопустимое соотношение сторон: {ratio}"}

    litellm_model, provider_cfg = resolve_model(model)
    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "prompt": prompt,
        "size": _ratio_to_size(ratio),
        "response_format": "b64_json",
        "num_retries": 0,
        "timeout": 120,
    }
    kwargs.update(provider_credentials(provider_cfg))

    started = time.monotonic()
    try:
        response = await litellm.aimage_generation(**kwargs)
    except Exception as e:
        status = 429 if _is_rate_limit(e) else getattr(e, "status_code", None)
        return {"error": True, "status": status, "msg": str(e)}

    data = (getattr(response, "data", None) or [None])[0]
    b64 = getattr(data, "b64_json", None) if data else None
    url = getattr(data, "url", None) if data else None

    if b64:
        file_bytes = base64.b64decode(b64)
    elif url:
        # Провайдер проигнорировал response_format и вернул ссылку
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return {
                            "error": True,
                            "status": resp.status,
                            "msg": f"Не удалось скачать изображение: HTTP {resp.status}",
                        }
                    file_bytes = await resp.read()
        except Exception as e:
            return {"error": True, "msg": f"Не удалось скачать изображение: {e}"}
    else:
        return {"error": True, "msg": "Провайдер не вернул изображение"}

    return {
        "error": False,
        "file": file_bytes,
        "elapsed_time": time.monotonic() - started,
    }


async def _litellm_call(
    model_id: str,
    messages: list,
    *,
    stream: bool,
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: str = "auto",
    timeout: float = 30.0,
):
    litellm_model, provider_cfg = resolve_model(model_id)
    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "messages": messages,
        "stream": stream,
        "num_retries": 0,
        "timeout": timeout,
    }
    kwargs.update(provider_credentials(provider_cfg))
    if tools is not None:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice

    return await litellm.acompletion(**kwargs)


async def stream_text_api(
    model: str,
    messages: list[dict[str, Any]],
    tools: Optional[list[dict[str, Any]]] = None,
    tool_choice: str = "auto",
    fallbacks: list[str] | None = None,
    user_tier: int = 0,
) -> AsyncGenerator[tuple[str, str], None]:

    candidates = _build_candidates(model, fallbacks, user_tier)
    last_exc: BaseException | None = None

    for candidate in candidates:
        if not await check_rpm_limit(candidate):
            last_exc = LocalRateLimitError("Превышен лимит для данной модели.")
            if candidate == candidates[-1]:
                raise last_exc
            continue

        try:
            stream = await _litellm_call(
                candidate,
                messages,
                stream=True,
                tools=tools,
                tool_choice=tool_choice,
            )
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e):
                continue
            _mark_model_failed(candidate, e)
            continue

        try:
            received_content = False
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None) if delta else None
                if content:
                    received_content = True
                    yield content, candidate
            if received_content:
                _mark_model_succeeded(candidate)
            return
        except Exception as e:
            logger.warning(
                f"⚠️ Стрим модели {candidate} прерван: {type(e).__name__}: {e}"
            )
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Нет доступных моделей для запроса")


async def simple_text_api(
    model: str,
    messages: list,
    fallbacks: list[str] | None = None,
    user_tier: int = 0,
) -> tuple[str, str]:
    candidates = _build_candidates(model, fallbacks, user_tier)
    last_exc: BaseException | None = None

    for candidate in candidates:
        if not await check_rpm_limit(candidate):
            last_exc = LocalRateLimitError("Превышен лимит для данной модели.")
            if candidate == candidates[-1]:
                raise last_exc
            continue

        try:
            response = await _litellm_call(candidate, messages, stream=False)
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e):
                continue
            _mark_model_failed(candidate, e)
            continue

        choices = getattr(response, "choices", None) or []
        if not choices:
            last_exc = RuntimeError(f"Пустой ответ от {candidate}")
            _mark_model_failed(candidate, last_exc)
            continue

        content = getattr(choices[0].message, "content", None)
        if not content:
            last_exc = RuntimeError(f"Пустой content от {candidate}")
            _mark_model_failed(candidate, last_exc)
            continue

        _mark_model_succeeded(candidate)
        return content, candidate

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Нет доступных моделей для запроса")


async def tools_text_api(
    model: str,
    messages: list,
    tools: list[dict[str, Any]],
    tool_choice: str = "auto",
    fallbacks: list[str] | None = None,
    user_tier: int = 0,
) -> tuple[Any, str]:
    """Не-стриминговый вызов с function calling.

    Возвращает (message, candidate): message — объект ответа целиком,
    в нём может быть либо content, либо tool_calls.
    """
    candidates = _build_candidates(model, fallbacks, user_tier)
    last_exc: BaseException | None = None

    for candidate in candidates:
        if not await check_rpm_limit(candidate):
            last_exc = LocalRateLimitError("Превышен лимит для данной модели.")
            if candidate == candidates[-1]:
                raise last_exc
            continue

        try:
            response = await _litellm_call(
                candidate, messages, stream=False, tools=tools, tool_choice=tool_choice
            )
        except Exception as e:
            last_exc = e
            if _is_rate_limit(e):
                continue
            _mark_model_failed(candidate, e)
            continue

        choices = getattr(response, "choices", None) or []
        if not choices:
            last_exc = RuntimeError(f"Пустой ответ от {candidate}")
            _mark_model_failed(candidate, last_exc)
            continue

        resp_message = choices[0].message
        has_payload = getattr(resp_message, "content", None) or getattr(
            resp_message, "tool_calls", None
        )
        if not has_payload:
            last_exc = RuntimeError(f"Ни content, ни tool_calls от {candidate}")
            _mark_model_failed(candidate, last_exc)
            continue

        _mark_model_succeeded(candidate)
        return resp_message, candidate

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Нет доступных моделей для запроса")


async def simple_text_api_text(
    model: str,
    messages: list,
    fallbacks: list[str] | None = None,
    user_tier: int = 0,
) -> str:
    text, _ = await simple_text_api(model, messages, fallbacks, user_tier)
    return text


async def ocr_process_api(file_bytes: bytes, file_ext: str = "jpg") -> str:
    if not JIGSAW_API_KEY:
        raise ValueError("JIGSAW_API_KEY не найден в переменных окружения.")

    url = "https://api.jigsawstack.com/v1/vocr"
    form = aiohttp.FormData()

    content_type = f"image/{'jpeg' if file_ext.lower() == 'jpg' else file_ext.lower()}"
    form.add_field(
        "file",
        value=file_bytes,
        filename=f"image.{file_ext}",
        content_type=content_type,
    )

    payload = {
        "prompt": "Extract all visible text from the image exactly as it appears, line by line."
    }
    form.add_field("body", value=json.dumps(payload), content_type="application/json")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, data=form, headers={"x-api-key": JIGSAW_API_KEY}
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
    """Проверка доступности моделей"""
    async with _model_health_lock:
        await _load_model_health()
        now = time.time()

        all_api_models = get_all_models()
        current_tier = int(os.getenv("ONLYSQ_TIER", 0))

        if not _model_health and not force_refresh:
            try:
                cached_result = await redis_db.client.get(_MODEL_LIST_CACHE_KEY)
                if cached_result:
                    checked_models = json.loads(cached_result)
                    if isinstance(checked_models, dict):
                        filtered_models.clear()
                        filtered_models.update(checked_models)
                        for model_id in checked_models:
                            _model_health[model_id] = {
                                "available": True,
                                "checked_at": now,
                                "error": None,
                            }
                        await _save_model_health()
                        logger.info(
                            f"💾 Мигрирован старый кэш моделей: {len(checked_models)}"
                        )
                        return
            except Exception as e:
                logger.warning(f"⚠️ Ошибка миграции кэша моделей: {e}")

        test_messages = [{"role": "user", "content": "Write hello world"}]
        checked_count = 0
        skipped_count = 0

        # Итерируемся по всем моделям из нового JSON
        for model_id, model in all_api_models.items():
            if tier_filtered and model.get("is_premium") and current_tier == 0:
                continue

            state = _model_health.get(model_id)
            success_cooldown, failure_cooldown = healthcheck_cooldowns(model_id)
            cooldown = (
                success_cooldown
                if not state or state.get("available", False)
                else failure_cooldown
            )
            is_due = (
                force_refresh
                or state is None
                or now - float(state.get("checked_at", 0)) >= cooldown
            )

            if not healthcheck_enabled(model_id):
                _model_health[model_id] = {
                    "available": True,
                    "checked_at": now,
                    "error": None,
                }
                continue

            if not is_due:
                skipped_count += 1
                continue

            modality = model.get("modality", "text")
            if modality == "image" and not include_image:
                if state is None:
                    _model_health[model_id] = {
                        "available": True,
                        "checked_at": now,
                        "error": None,
                    }
                continue

            checked_count += 1
            logger.info(
                f"⌛️ Проверяем модель {model_id} (Провайдер: {model.get('provider_name')})"
            )
            try:
                if modality == "text":
                    response = await _litellm_call(
                        model_id, test_messages, stream=False
                    )
                    choices = getattr(response, "choices", None) or []
                    content = (
                        getattr(choices[0].message, "content", None)
                        if choices
                        else None
                    )
                    if not content or len(str(content)) <= 5:
                        raise RuntimeError("пустой или слишком короткий ответ")

                elif modality == "image":
                    api_resp = await generate_image_api(model_id, "Ginger cat")
                    if api_resp.get("error"):
                        raise RuntimeError(f"API вернуло ошибку: {api_resp.get('msg')}")
                    image_bytes = api_resp.get("file")
                    if not image_bytes or not isinstance(image_bytes, bytes):
                        raise RuntimeError("поле file пустое или имеет неверный формат")
                    mime = magic.from_buffer(image_bytes, mime=True)
                    if not mime.startswith("image/"):
                        raise RuntimeError("модель не вернула изображение")

                _model_health[model_id] = {
                    "available": True,
                    "checked_at": now,
                    "error": None,
                }
            except Exception as e:
                _model_health[model_id] = {
                    "available": False,
                    "checked_at": now,
                    "error": f"{type(e).__name__}: {e}",
                }
                logger.warning(f"⚠️ Модель {model_id} не ответила: {e}")

        checked_models: dict[str, dict] = {}
        for model_id, model in all_api_models.items():
            if model.get("hidden"):
                continue
            state = _model_health.get(model_id)
            if not state or not state.get("available", False):
                continue
            if tier_filtered and model.get("is_premium") and current_tier == 0:
                continue
            checked_models[model_id] = model

        filtered_models.clear()
        filtered_models.update(checked_models)
        await _save_model_health()

        try:
            await redis_db.client.set(
                _MODEL_LIST_CACHE_KEY, json.dumps(checked_models, ensure_ascii=False)
            )
        except Exception as e:
            logger.warning(f"⚠️ Ошибка сохранения списка моделей: {e}")

        logger.info(
            f"✅ Healthcheck завершён: проверено {checked_count}, cooldown {skipped_count}, доступно {len(checked_models)}"
        )


async def get_ai_sector_impacts(
    sectors: list[str], news: list[str]
) -> dict[str, float]:
    result: dict[str, float] = {s: 0.0 for s in sectors}

    if not sectors or not news:
        return result

    model = "gemini-3.1-flash-lite"
    news_block = "\n".join(f"- {n}" for n in news)
    sector_list = ", ".join(sectors)

    system_prompt = (
        "Ты — финансовый аналитик игрового рынка акций. На вход тебе будет "
        "приходить ТОЛЬКО пачка свежих финансовых новостей. Твоя задача — "
        "самостоятельно определить, какие новости относятся к каким секторам "
        "из фиксированного списка ниже, и оценить совокупное влияние на "
        "каждый сектор.\n\n"
        f"Секторы (используй ровно эти ключи в ответе): {sector_list}.\n\n"
        "Отвечай СТРОГО валидным JSON без какого-либо дополнительного текста, "
        'в формате {"impacts": {"<sector>": <float>, ...}}, где значение — '
        "относительное влияние на сектор в диапазоне от -0.05 до 0.05 "
        "(отрицательное — негатив, положительное — позитив).\n\n"
        "ВАЖНО: если по сектору НЕТ релевантных новостей либо они "
        "нейтральны/несущественны — верни для него 0.0. Значение 0.0 "
        "означает, что momentum этого сектора вообще НЕ нужно трогать — "
        "это нормальный и предпочтительный исход. Не выдумывай влияние ради "
        "заполнения. В ответе обязательно перечисли все секторы из списка. "
        "Будь консервативным: оценивай только явные и значимые сигналы; "
        "слабые, спорные или нейтральные новости → 0.0."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Новости:\n{news_block}"},
    ]

    try:
        response = await simple_text_api(model, messages)
    except LocalRateLimitError as e:
        logger.warning(f"⚠️ AI sector sentiment rate-limit: {e}")
        return result
    except Exception as e:
        logger.warning(f"⚠️ AI sector sentiment недоступен: {e}")
        return result

    if not response:
        return result

    match = re.search(r"\{.*\}", response, re.DOTALL)
    if not match:
        return result

    try:
        data = json.loads(match.group(0))
        impacts = data.get("impacts", {}) or {}
    except Exception as e:
        logger.warning(
            f"⚠️ Не удалось распарсить sector sentiment: {e} | raw={response!r}"
        )
        return result

    for sector in result.keys():
        try:
            val = float(impacts.get(sector, 0.0))
        except (TypeError, ValueError):
            val = 0.0
        result[sector] = max(-0.05, min(0.05, val))

    return result


async def check_rpm_limit(model_id: str) -> bool:
    """
    TODO: Лимиты в новом конфиге представлены в виде free_tokens_day / free_tokens_week.
    Для их подсчета требуется контекст пользователя (user_id), поэтому эта функция
    пока возвращает True. Полноценный контроль токенов нужно реализовать в хэндлерах.
    """
    return True
