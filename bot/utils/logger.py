import logging
import sys

def setup_logger():
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    root_logger.addHandler(handler)
    return root_logger


