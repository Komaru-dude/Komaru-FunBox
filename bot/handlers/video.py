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
CODEC_ALIASES = {
    "h264": ["avc1", "h264"],
    "vp9": ["vp9"],
    "av01": ["av01"],
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
        "--no-cache-dir",
        "-j",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output_text = stdout.decode(errors="replace")
    logger.debug(f"🔄 yt-dlp -j вывод: {output_text}")

    if proc.returncode != 0:
        logger.warning(f"📛 Ошибка yt-dlp: {stderr.decode(errors='ignore')[:200]}")
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.exception(f"📛 Не удалось декодировать JSON: {e}")
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


def find_best_format(
    formats: List[dict],
    duration_s: Optional[int],
    size_limit_mb: Optional[float],
    quality: str = "medium",
) -> Optional[str]:
    """
    Выбирает наилучший формат видео на основе явного списка приоритетов.
    """
    # Список приоритетов: (макс. высота, кодек). От лучшего к худшему.
    SEARCH_PRIORITIES = {
        "low": [(480, "h264"), (360, "h264")],
        "medium": [(720, "h264"), (480, "h264")],
        "high": [(1080, "h264"), (720, "h264")],
    }

    video_only, audio_only, muxed = [], [], []
    for fmt in formats:
        has_video = fmt.get("vcodec") and fmt.get("vcodec") != "none"
        has_audio = fmt.get("acodec") and fmt.get("acodec") != "none"
        if has_video and has_audio:
            muxed.append(fmt)
        elif has_video:
            video_only.append(fmt)
        elif has_audio:
            audio_only.append(fmt)

    logger.debug(f"Качество: {quality}, Форматов: {len(formats)}")
    logger.debug(f"Видео-только: {len(video_only)}, Аудио-только: {len(audio_only)}")

    if quality == "audio":
        audio_only = sorted(
            [
                f
                for f in formats
                if f.get("acodec") != "none"
                and (not f.get("vcodec") or f.get("vcodec") == "none")
                and f.get("filesize") is not None
                and f["filesize"] <= 50 * 1024 * 1024  # <= 50 МБ в байтах
            ],
            key=lambda x: x.get("abr", 0),
            reverse=True,
        )
        if audio_only:
            return str(audio_only[0]["format_id"])
        return None

    best_audio = max(audio_only, key=lambda x: x.get("abr", 0), default=None)
    best_audio_size_mb = (
        estimate_size_mb_from_format(best_audio, duration_s) if best_audio else 0
    )

    for max_height, codec in SEARCH_PRIORITIES.get(quality, []):
        codec_check = CODEC_ALIASES.get(codec, [codec])

        candidates = sorted(
            [
                f
                for f in muxed
                if any(c in f.get("vcodec", "") for c in codec_check)
                and f.get("height", 0) <= max_height
            ],
            key=lambda x: x.get("height", 0),
            reverse=True,
        )
        if candidates:
            best_candidate = candidates[0]
            est_size = estimate_size_mb_from_format(best_candidate, duration_s)
            if size_limit_mb is None or (
                est_size is not None and est_size <= size_limit_mb
            ):
                return str(best_candidate["format_id"])

        if best_audio:
            candidates = sorted(
                [
                    v
                    for v in video_only
                    if any(c in v.get("vcodec", "") for c in codec_check)
                    and v.get("height", 0) <= max_height
                ],
                key=lambda x: x.get("height", 0),
                reverse=True,
            )
            if candidates:
                best_video = candidates[0]
                video_size_mb = estimate_size_mb_from_format(best_video, duration_s)
                if not video_size_mb:
                    continue

                total_size = video_size_mb + (best_audio_size_mb or 0)
                if size_limit_mb is None or total_size <= size_limit_mb:
                    return f"{best_video['format_id']}+{best_audio['format_id']}"

    if best_audio:
        audio_size_mb = estimate_size_mb_from_format(best_audio, duration_s)
        if size_limit_mb is None or (
            est_size is not None and est_size <= size_limit_mb
        ):
            return str(best_audio["format_id"])
    return None


async def download_with_format(
    url: str, format_spec: str, output_path: Path
) -> Tuple[bool, str]:
    """Скачивание видео с указанным форматом."""
    try:
        logger.debug(f"🎛 Используем формат: {format_spec}")
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--no-cache-dir",
            "-f",
            format_spec,
            "--embed-metadata",
            "--embed-thumbnail",
            "-o",
            str(output_path),
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        stdout, _ = await proc.communicate()
        output_text = stdout.decode(errors="replace")
        logger.debug(f"🌀 Вывод yt-dlp:\n{output_text}")

        if proc.returncode == 0 and output_path.exists():
            return True, stdout.decode(errors="ignore") or "OK"
        else:
            return False, stdout.decode(errors="ignore") or "Неизвестная ошибка"

    except Exception as e:
        return False, str(e)


@video_router.message(Command("youtube"), CooldownFilter("video", 300))
async def cmd_video(message: Message, bot: Bot, url=None):
    if not url:
        parts = message.text.split(maxsplit=1)
        url = parts[1] if len(parts) > 1 else None

    if not url:
        return await message.reply("❌ Укажите URL видео: /youtube <ссылка>")

    # Извлекаем ID видео
    video_id = extract_youtube_id(url)
    if not video_id:
        return await message.reply("❌ Некорректная ссылка на YouTube-видео.")

    # Создаём "чистый" URL для yt-dlp, чтобы избежать проблем
    clean_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        await message.answer("⏳ Анализ видео...")
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
                        text="💾 Низкое",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="low"
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="💿 Среднее",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="medium"
                        ).pack(),
                    ),
                    InlineKeyboardButton(
                        text="📀 Высокое",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="high"
                        ).pack(),
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🎧 Только аудио",
                        callback_data=VideoQualityCallback(
                            url_id=video_id, quality="audio"
                        ).pack(),
                    )
                ],
            ]
        )

        text = f"🎬 {info.get('title', 'Без названия')}\n"
        text += f"⏱ Длительность: {duration_min} мин\n"
        text += "📝 Выберите качество:\n"
        if duration_min > MAX_DURATION_MINUTES:
            text += f"⚠️ Видео >{MAX_DURATION_MINUTES} мин - качество будет понижено\n"

        await message.reply(text, reply_markup=keyboard)
    except Exception:
        await error_report(message, bot, "video_cmd", traceback.format_exc())


@video_router.callback_query(VideoQualityCallback.filter())
async def quality_chosen_handler(
    callback: CallbackQuery, callback_data: VideoQualityCallback, bot: Bot
):
    """Обработка выбора качества."""
    # Получаем ID из колбэк-данных
    video_id = callback_data.url_id
    # Создаём полный URL для yt-dlp
    url = f"https://www.youtube.com/watch?v={video_id}"
    quality = callback_data.quality

    await callback.message.edit_text("⏳ Начинаю обработку...")
    temp_file = None
    is_audio = quality == "audio"

    try:
        await callback.message.edit_text("🔍 Получение информации...")
        info = await yt_dlp_json(url)

        if not info:
            return await callback.message.edit_text("❌ Ошибка получения данных")

        duration_min = (info.get("duration") or 0) // 60
        if duration_min > MAX_DURATION_MINUTES and quality != "low" and not is_audio:
            quality = "low"
            await callback.message.answer(
                f"⚠️ Видео слишком длинное. Установлено качество: Low"
            )

        format_spec = find_best_format(
            formats=info.get("formats", []),
            duration_s=info.get("duration"),
            size_limit_mb=TELEGRAM_MAX_MB,
            quality=quality,
        )

        if not format_spec:
            return await callback.message.edit_text(
                "📛 Формат до 50 МБ не найден.\n💡 Попробуйте выбрать другое качество"
            )

        await callback.message.edit_text(f"⬇️ Скачивание ({quality})...")
        file_ext = ".mp3" if is_audio else ".mp4"
        temp_file = CACHE_DIR / f"{uuid.uuid4()}{file_ext}"

        success, log = await download_with_format(url, format_spec, temp_file)
        if not success:
            return await callback.message.edit_text(
                f"❌ Ошибка скачивания, попробуйте через несколько часов или обратитесь к разработчику"
            )

        file_size = temp_file.stat().st_size / (1024**2)
        if file_size > TELEGRAM_MAX_MB:
            return await callback.message.edit_text(
                f"⚠️ Файл слишком большой ({file_size:.1f}MB > {TELEGRAM_MAX_MB}MB)"
            )

        await callback.message.edit_text("📤 Отправка...")
        if is_audio:
            await callback.message.reply_audio(
                FSInputFile(temp_file), caption=f"✅ Только аудио"
            )
        else:
            await callback.message.reply_video(
                FSInputFile(temp_file), caption=f"✅ {quality.capitalize()} качество"
            )

    except Exception as e:
        await error_report(callback.message, bot, "video_download", str(e))
    finally:
        if temp_file and temp_file.exists():
            temp_file.unlink()


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
        await message.reply("🔄 Обработка...")
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
