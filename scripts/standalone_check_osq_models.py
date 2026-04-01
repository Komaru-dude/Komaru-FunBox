# vibecoded
import argparse
import asyncio
import json
import os
from typing import Any, Dict

import aiohttp
import openai
from dotenv import load_dotenv

MODELS_URL_DEFAULT = "https://api.onlysq.ru/ai/models"


def load_env() -> None:
    try:
        load_dotenv()
    except Exception:
        pass


async def fetch_models(session: aiohttp.ClientSession, api_key: str) -> Dict[str, Any]:
    url = os.getenv("ONLYSQ_MODELS_URL", MODELS_URL_DEFAULT)
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with session.get(url, headers=headers) as resp:
        resp.raise_for_status()
        return await resp.json()


async def check_text_model(
    client: openai.AsyncOpenAI, model_id: str
) -> tuple[bool, str]:
    try:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Write hello world"}],
            stream=False,
        )
        if not response.choices:
            return False, "нет вариантов ответа"
        content = response.choices[0].message.content
        if not content:
            return False, "пустой ответ"
        return True, "ок"
    except Exception as exc:
        return False, f"ошибка: {exc}"


async def check_image_model(
    session: aiohttp.ClientSession, model_id: str, api_key: str
) -> tuple[bool, str]:
    imagen_url = os.getenv("IMAGEN_API_URL")
    if not imagen_url:
        return False, "IMAGEN_API_URL не задан"
    if not api_key:
        return False, "ONLYSQ_API_KEY не задан"

    payload = {"model": model_id, "prompt": "Ginger cat", "ratio": "1:1"}
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with session.post(imagen_url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                return False, f"HTTP {resp.status}: {await resp.text()}"
            data = await resp.json()
            if data.get("files"):
                return True, "ок"
            return False, "нет файлов в ответе"
    except Exception as exc:
        return False, f"ошибка: {exc}"


async def check_model(
    model_id: str,
    model_info: Dict[str, Any],
    client: openai.AsyncOpenAI,
    session: aiohttp.ClientSession,
    current_tier: int,
    ignore_tier: bool,
    text_only: bool,
    image_only: bool,
    semaphore: asyncio.Semaphore,
    api_key: str,
) -> None:
    async with semaphore:
        name = model_info.get("name", "unknown")
        modality = model_info.get("modality", "unknown")
        model_tier = int(model_info.get("tier", 0))
        api_status = model_info.get("status", "unknown")
        can_stream = model_info.get("can-stream", False)
        can_tools = model_info.get("can-tools", False)
        can_think = model_info.get("can-think", False)
        cost = model_info.get("cost", "?")
        owner = model_info.get("owner", "unknown")

        if not ignore_tier and model_tier > current_tier:
            print(
                f"{model_id} | {name} | {modality} | tier {model_tier} | "
                f"api {api_status} | stream {can_stream} | tools {can_tools} | "
                f"think {can_think} | cost {cost} | owner {owner} | "
                f"проверка: пропуск (tier {model_tier} > {current_tier})"
            )
            return

        if text_only and modality != "text":
            print(
                f"{model_id} | {name} | {modality} | tier {model_tier} | "
                f"api {api_status} | stream {can_stream} | tools {can_tools} | "
                f"think {can_think} | cost {cost} | owner {owner} | "
                "проверка: пропуск (только текстовые)"
            )
            return
        if image_only and modality != "image":
            print(
                f"{model_id} | {name} | {modality} | tier {model_tier} | "
                f"api {api_status} | stream {can_stream} | tools {can_tools} | "
                f"think {can_think} | cost {cost} | owner {owner} | "
                "проверка: пропуск (только изображения)"
            )
            return

        if modality == "text":
            ok, detail = await check_text_model(client, model_id)
        elif modality == "image":
            ok, detail = await check_image_model(session, model_id, api_key)
        else:
            print(
                f"{model_id} | {name} | {modality} | tier {model_tier} | "
                f"api {api_status} | stream {can_stream} | tools {can_tools} | "
                f"think {can_think} | cost {cost} | owner {owner} | "
                f"проверка: пропуск (неизвестная модальность: {modality})"
            )
            return

        status = "ок" if ok else "ошибка"
        print(
            f"{model_id} | {name} | {modality} | tier {model_tier} | "
            f"api {api_status} | stream {can_stream} | tools {can_tools} | "
            f"think {can_think} | cost {cost} | owner {owner} | "
            f"проверка: {status} ({detail})"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Асинхронная проверка доступности моделей OnlySQ",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Проверять только текстовые модели",
    )
    parser.add_argument(
        "--image-only",
        action="store_true",
        help="Проверять только модели изображений",
    )
    parser.add_argument(
        "--ignore-tier",
        action="store_true",
        help="Игнорировать ONLYSQ_TIER при проверке",
    )
    return parser.parse_args()


async def main() -> int:
    load_env()

    args = parse_args()
    if args.text_only and args.image_only:
        print("Используйте только один из аргументов --text-only или --image-only")
        return 2

    api_key = os.getenv("ONLYSQ_API_KEY", "")
    if not api_key:
        print("ONLYSQ_API_KEY не задан")
        return 1
    base_url = os.getenv("OPENAI_SDK_API_URL")
    if not base_url:
        print("OPENAI_SDK_API_URL не задан")
        return 1

    current_tier = int(os.getenv("ONLYSQ_TIER", "0"))

    client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
    semaphore = asyncio.Semaphore(5)

    async with aiohttp.ClientSession() as session:
        models_payload = await fetch_models(session, api_key)

        all_models = models_payload.get("models", {})
        if not all_models:
            print("API не вернул список моделей")
            return 1

        tasks = []
        for model_id in sorted(all_models.keys()):
            model_info = all_models.get(model_id)
            if not model_info:
                print(
                    f"{model_id} | неизвестно | unknown | tier ? | api ? | "
                    "stream ? | tools ? | think ? | cost ? | owner ? | "
                    "проверка: нет в ответе API"
                )
                continue
            tasks.append(
                check_model(
                    model_id,
                    model_info,
                    client,
                    session,
                    current_tier,
                    args.ignore_tier,
                    args.text_only,
                    args.image_only,
                    semaphore,
                    api_key,
                )
            )

        if tasks:
            await asyncio.gather(*tasks)

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
