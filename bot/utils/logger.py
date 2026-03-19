import logging
import sys
from pathlib import Path


def setup_logger(log_file: Path, level=logging.INFO):
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.addHandler(file_handler)

    logging.getLogger("pyrogram").setLevel(logging.WARNING)

    return root_logger
