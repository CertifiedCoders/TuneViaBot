import logging
import time
from logging.handlers import RotatingFileHandler

LOG_FILE = "log.txt"
LEVEL = logging.INFO
INCLUDE_SOURCE = False

formatter = logging.Formatter(
    "[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
    if not INCLUDE_SOURCE
    else "[%(asctime)s - %(levelname)s] - %(name)s - %(filename)s:%(lineno)d - %(message)s",
    "%d-%b-%y %H:%M:%S",
)
formatter.converter = time.gmtime  # Use UTC

stream = logging.StreamHandler()
stream.setFormatter(formatter)

file = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5MB
    backupCount=3,
    encoding="utf-8",
)
file.setFormatter(formatter)

root = logging.getLogger()
root.setLevel(LEVEL)
root.handlers.clear()
root.addHandler(stream)
root.addHandler(file)

for lib in ("pymongo", "httpx", "pyrogram", "pytgcalls"):
    l = logging.getLogger(lib)
    l.setLevel(logging.ERROR)
    l.propagate = False

ntg_logger = logging.getLogger("ntgcalls")
ntg_logger.setLevel(logging.CRITICAL)
ntg_logger.propagate = False

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)

root.info("Logging system initialized.")
