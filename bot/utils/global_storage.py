import asyncio
import json
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
ECONOMY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "eco_cfg.json"
SHOP_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "items.json"
FREE_GAMES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "epic_free_games.json"
)

active_chats = []
active_chats_lock = asyncio.Lock()

onlysq_models = {}

error_report_timestamps = []
error_report_lock = asyncio.Lock()

update_cache = {}

duel_sessions = {}
duel_sessions_lock = asyncio.Lock()


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


eco_config = load_config(ECONOMY_CONFIG_PATH)
shop_config = load_config(SHOP_CONFIG_PATH)
