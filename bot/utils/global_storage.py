import asyncio
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
ECONOMY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "eco_cfg.json"

active_chats = []
active_chats_lock = asyncio.Lock()

onlysq_models = {}

error_report_timestamps = []
error_report_lock = asyncio.Lock()

update_cache = {}


def load_economy_config() -> dict:
    with open(ECONOMY_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


eco_config = load_economy_config()
