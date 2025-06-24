import logging
from logging.handlers import RotatingFileHandler

LOG_FILE = "log.txt"
LEVEL = logging.INFO
INCLUDE_SOURCE = False

fmt = "[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
if INCLUDE_SOURCE:
    fmt = "[%(asctime)s - %(levelname)s] - %(name)s - %(filename)s:%(lineno)d - %(message)s"

formatter = logging.Formatter(fmt, "%d-%b-%y %H:%M:%S")

stream = logging.StreamHandler()
stream.setFormatter(formatter)

file = RotatingFileHandler(
    LOG_FILE,
    encoding="utf-8",
)
file.setFormatter(formatter)

root = logging.getLogger()
root.setLevel(LEVEL)
root.handlers.clear()
root.addHandler(stream)
root.addHandler(file)

for lib in ("pymongo", "httpx", "pyrogram", "pytgcalls", "ntgcalls"):
    logging.getLogger(lib).setLevel(logging.ERROR)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
