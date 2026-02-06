import base64
import json
import os

import aiohttp
import openai

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


async def generate_image_api(model: str, prompt: str, ratio: str = "1:1") -> dict:
    """Генерация изображений через внешний API."""
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


async def stream_text_api(model: str, messages: list):
    """Генератор для потоковой передачи текста."""
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def simple_text_api(model: str, messages: list) -> str:
    """Обычный запрос текста (без стриминга)."""
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
