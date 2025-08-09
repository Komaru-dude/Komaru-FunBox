import asyncio
import json
import re
import shutil
import traceback
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import logger
from bot.filters.cooldown_filter import CooldownFilter
from bot.utils.aio_tools import error_report
from bot.utils.global_storage import CACHE_DIR

video_router = Router()

# Настройки
MAX_DURATION_MINUTES = 5
TELEGRAM_MAX_MB = 50
CODEC_PRIORITY = ["av01", "vp9", "h264"]
QUALITY_PRESETS = {
    "low": {"max_height": 360},
    "medium": {"max_height": 720},
    "high": {"max_height": None},
}


class VideoQualityCallback(CallbackData, prefix="vidq", sep="|"):
    url_id: str
    quality: str


def extract_youtube_id(url: str) -> Optional[str]:
    """Извлекает уникальный ID видео из YouTube-ссылки."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",  # Стандартные ссылки
        r"youtu\.be\/([0-9A-Za-z_-]{11}).*",  # Ссылки youtu.be
        r"shorts\/([0-9A-Za-z_-]{11}).*",  # Ссылки Shorts
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def yt_dlp_json(url: str) -> Optional[dict]:
    """Получение метаданных видео через yt-dlp."""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-j",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.warning(f"yt-dlp error: {stderr.decode(errors='ignore')[:200]}")
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.exception(f"JSON decode error: {e}")
        return None


def estimate_size_mb_from_format(
    fmt: dict, duration_s: Optional[int]
) -> Optional[float]:
    """Оценка размера видео в мегабайтах."""
    # 1. Приоритет: явный размер файла
    for key in ("filesize", "filesize_approx"):
        if size := fmt.get(key):
            try:
                return float(size) / (1024**2)
            except (TypeError, ValueError):
                continue

    # 2. Расчет через битрейт
    if duration_s and (tbr := fmt.get("tbr")):
        try:
            return (float(tbr) * 1000 * float(duration_s)) / (8 * 1024**2)
        except (TypeError, ValueError):
            pass

    return None


def choose_best_format_pair(
    formats: List[dict],
    preferred_codecs: List[str],
    max_height: Optional[int],
    duration_s: Optional[int],
    size_limit_mb: Optional[float],
) -> Optional[str]:
    """Выбор оптимального формата видео."""

    def is_suitable_format(fmt: dict, codec: str) -> bool:
        """Проверка соответствия формата требованиям."""
        if fmt.get("acodec", "none") == "none" and fmt.get("vcodec") == "none":
            return False

        vcodec = fmt.get("vcodec", "")
        height = fmt.get("height")

        # Проверка кодека
        if codec not in vcodec:
            return False

        # Проверка высоты
        if max_height is not None and height and height > max_height:
            return False

        return True

    # Поиск муксованных форматов
    for codec in preferred_codecs:
        candidates = []
        for fmt in formats:
            if not is_suitable_format(fmt, codec):
                continue

            # Отбор муксованных форматов
            if fmt.get("acodec") != "none":
                est_size = estimate_size_mb_from_format(fmt, duration_s)
                candidates.append((fmt, est_size))

        if not candidates:
            continue

        # Сортировка по размеру/качеству
        if size_limit_mb:
            candidates = [c for c in candidates if c[1] and c[1] <= size_limit_mb]
            if not candidates:
                continue
            candidates.sort(key=lambda x: x[1])
        else:
            candidates.sort(key=lambda x: x[0].get("height", 0), reverse=True)

        return str(candidates[0][0]["format_id"])

    # Поиск раздельных форматов (видео + аудио)
    video_candidates = []
    audio_candidates = []

    for fmt in formats:
        if fmt.get("vcodec") not in (None, "none") and fmt.get("acodec") == "none":
            video_candidates.append(fmt)
        elif fmt.get("acodec") not in (None, "none") and fmt.get("vcodec") in (
            None,
            "none",
        ):
            audio_candidates.append(fmt)

    if not video_candidates or not audio_candidates:
        return None

    # Выбор лучшего аудио
    audio_candidates.sort(
        key=lambda a: a.get("asr", 0) or a.get("abr", 0), reverse=True
    )
    best_audio_id = audio_candidates[0]["format_id"]

    # Выбор видео с учетом ограничений
    suitable_videos = []
    for video in video_candidates:
        # Проверка кодека и высоты
        if not any(c in video.get("vcodec", "") for c in preferred_codecs):
            continue
        if max_height is not None and video.get("height", 0) > max_height:
            continue

        # Проверка размера
        video_size = estimate_size_mb_from_format(video, duration_s)
        audio_size = estimate_size_mb_from_format(audio_candidates[0], duration_s)
        total_size = (video_size or 0) + (audio_size or 0)

        if size_limit_mb and total_size > size_limit_mb:
            continue

        suitable_videos.append((video, total_size))

    if not suitable_videos:
        return None

    # Сортировка по качеству
    suitable_videos.sort(key=lambda x: x[0].get("height", 0), reverse=True)
    return f"{suitable_videos[0][0]['format_id']}+{best_audio_id}"


async def download_with_format(
    url: str, format_spec: str, output_path: Path
) -> Tuple[bool, str]:
    """Скачивание видео с указанным форматом."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f",
            format_spec,
            "-o",
            str(output_path),
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and output_path.exists():
            return True, stdout.decode()
        return False, stderr.decode()
    except Exception as e:
        return False, str(e)


@video_router.message(Command("youtube"), CooldownFilter("video", 150))
async def cmd_video(message: Message, bot: Bot, url=None):
    if not url:
        parts = message.text.split(maxsplit=1)
        url = parts[1] if len(parts) > 1 else None

    if not url:
        return await message.reply("❌ Укажите URL видео: /video <ссылка>")

    # Извлекаем ID видео
    video_id = extract_youtube_id(url)
    if not video_id:
        return await message.reply("❌ Некорректная ссылка на YouTube-видео.")

    # Создаём "чистый" URL для yt-dlp, чтобы избежать проблем
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        msg = await message.answer("⏳ Анализ видео...")
        info = await yt_dlp_json(clean_url)

        if not info:
            await error_report(message, bot, "video_info", "Ошибка получения данных")
            return await message.reply("❌ Не удалось получить информацию о видео")

        if info.get("is_live"):
            return await message.reply("❌ Нельзя загружать прямые трансляции.")

        if "/shorts/" in url:
            return await message.reply("❌ Нельзя загружать YouTube Shorts.")

        duration = int(info.get("duration", 0))
        duration_min = duration // 60

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Low",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="low"
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="Medium",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="medium"
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="High",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="high"
                        ).pack(),
                    ),
                ]
            ]
        )

        text = f"🎬 *{info.get('title', 'Без названия')}*\n"
        text += f"⏱ Длительность: {duration_min} мин\n"
        if duration_min > MAX_DURATION_MINUTES:
            text += f"⚠️ Видео >{MAX_DURATION_MINUTES} мин - качество будет понижено\n"

        await message.reply(text, reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "video_cmd", traceback.format_exc())
    finally:
        if "msg" in locals():
            await msg.delete()


@video_router.callback_query(VideoQualityCallback.filter())
async def quality_chosen_handler(
    callback: CallbackQuery, callback_data: VideoQualityCallback, bot: Bot
):
    """Обработка выбора качества."""
    # Получаем ID из колбэк-данных
    video_id = callback_data.url
    # Создаём полный URL для yt-dlp
    url = f"https://www.youtube.com/watch?v={video_id}"
    quality = callback_data.quality

    await callback.answer("⏳ Начинаю обработку...")
    temp_file = None

    try:
        msg = await callback.message.edit_text("🔍 Получение информации...")
        info = await yt_dlp_json(url)

        if not info:
            return await callback.message.edit_text("❌ Ошибка получения данных")

        duration_min = (info.get("duration") or 0) // 60
        if duration_min > MAX_DURATION_MINUTES and quality != "low":
            quality = "low"
            await callback.message.answer(
                f"⚠️ Видео слишком длинное. Установлено качество: Low"
            )

        format_spec = choose_best_format_pair(
            formats=info.get("formats", []),
            preferred_codecs=CODEC_PRIORITY,
            max_height=QUALITY_PRESETS[quality]["max_height"],
            duration_s=info.get("duration"),
            size_limit_mb=TELEGRAM_MAX_MB,
        )

        if not format_spec:
            return await callback.message.edit_text("❌ Нет подходящих форматов")

        await callback.message.edit_text(f"⬇️ Скачивание ({quality})...")
        temp_file = CACHE_DIR / f"{uuid.uuid4()}.mp4"

        success, log = await download_with_format(url, format_spec, temp_file)
        if not success:
            return await callback.message.edit_text(
                f"❌ Ошибка скачивания: {log[:300]}"
            )

        file_size = temp_file.stat().st_size / (1024**2)
        if file_size > TELEGRAM_MAX_MB:
            return await callback.message.edit_text(
                f"⚠️ Файл слишком большой ({file_size:.1f}MB > {TELEGRAM_MAX_MB}MB)"
            )

        await callback.message.edit_text("📤 Отправка...")
        await callback.message.reply_video(
            FSInputFile(temp_file), caption=f"✅ {quality.capitalize()} качество"
        )

    except Exception as e:
        await error_report(callback.message, bot, "video_download", str(e))
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()
        if "msg" in locals() and msg:
            await msg.delete()


@video_router.message(Command("gif"), CooldownFilter("gif", 300))
async def cmd_gif(message: Message, bot: Bot):
    """Конвертация видео в GIF."""
    # Поиск видео в сообщении
    video = message.video or (
        message.reply_to_message.video if message.reply_to_message else None
    )

    if not video:
        return await message.reply("❌ Отправьте или ответьте на видео")

    temp_files = []
    try:
        # Скачивание видео
        msg = await message.reply("🔄 Обработка...")
        file = await bot.get_file(video.file_id)
        video_path = CACHE_DIR / f"{video.file_id}.mp4"
        temp_files.append(video_path)
        await bot.download_file(file.file_path, destination=video_path)

        # Конвертация в GIF
        gif_path = CACHE_DIR / f"{video.file_id}.gif"
        frames_dir = CACHE_DIR / f"{video.file_id}_frames"
        temp_files.extend([gif_path, frames_dir])

        # Извлечение кадров
        frames_dir.mkdir(exist_ok=True)
        frame_pattern = frames_dir / "frame_%04d.png"

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            "fps=15,scale=480:-1:flags=lanczos",
            "-compression_level",
            "0",
            str(frame_pattern),
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError("Ошибка извлечения кадров")

        # Создание GIF
        proc = await asyncio.create_subprocess_exec(
            "gifski",
            "--fps",
            "15",
            "-o",
            str(gif_path),
            *sorted(frames_dir.glob("*.png")),
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        if not gif_path.exists():
            raise RuntimeError("Ошибка создания GIF")

        # Отправка результата
        await message.reply_animation(FSInputFile(gif_path))
    except Exception as e:
        await error_report(message, bot, "gif", str(e))
    finally:
        # Очистка временных файлов
        for path in temp_files:
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
            except Exception:
                pass
        if "msg" in locals():
            await msg.delete()
