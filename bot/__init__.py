import logging
import os
import subprocess

from dotenv import load_dotenv

from .utils.logger import setup_logger

load_dotenv()

dir_path = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(dir_path)
data_dir = os.path.join(parent_dir, "data")
PYRO_HOST = "127.0.0.1"
PYRO_PORT = os.getenv("PYRO_PORT")
API_URL = f"http://{PYRO_HOST}:{PYRO_PORT}"


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
is_test = branch_name == "test"
if is_test:
    level = logging.DEBUG
else:
    level = logging.INFO
logger = setup_logger(level)

if not os.path.exists(data_dir):
    os.mkdir(data_dir)
