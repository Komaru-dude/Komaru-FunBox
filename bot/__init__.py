import logging
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from .utils.logger import setup_logger

load_dotenv()

dir_path = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(dir_path)
PYRO_HOST = "127.0.0.1"
PYRO_PORT = os.getenv("PYRO_PORT")
API_URL = f"http://{PYRO_HOST}:{PYRO_PORT}"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CACHE_DIR = BASE_DIR / "cache"
ECONOMY_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "eco_cfg.json"
SHOP_CONFIG_PATH = BASE_DIR / "config" / "items.json"
FREE_GAMES_PATH = DATA_DIR / "epic_free_games.json"
COMMANDS_DIR = BASE_DIR / "config" / "commands"
STOCKS_PATH = DATA_DIR / "stocks.json"


def get_git_branch(path):
    try:
        return (
            subprocess.check_output(
                ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return None


branch_name = get_git_branch(parent_dir)
IS_TEST = branch_name == "test"
if IS_TEST:
    level = logging.DEBUG
else:
    level = logging.INFO
logger = setup_logger(level)

for path in (DATA_DIR, CACHE_DIR, COMMANDS_DIR):
    path.mkdir(parents=True, exist_ok=True)
