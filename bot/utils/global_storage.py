import asyncio
import json
from pathlib import Path
from typing import Union

from bot import ECONOMY_CONFIG_PATH, SHOP_CONFIG_PATH

active_chats = []
active_chats_lock = asyncio.Lock()

onlysq_models = {}

error_report_timestamps = []
error_report_lock = asyncio.Lock()

update_cache = {}

duel_sessions = {}
duel_sessions_lock = asyncio.Lock()


def load_config(path: Union[str, Path]) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


eco_config = load_config(ECONOMY_CONFIG_PATH)
shop_config = load_config(SHOP_CONFIG_PATH)
