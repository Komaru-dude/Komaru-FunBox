import asyncio
from pathlib import Path

active_chats = []
active_chats_lock = asyncio.Lock()

onlysq_models = {}

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

error_report_timestamps = []
error_report_lock = asyncio.Lock()
