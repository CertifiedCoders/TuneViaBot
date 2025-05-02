import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt"),
        logging.StreamHandler(),
    ],
)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)


ntgcalls_logger = logging.getLogger("ntgcalls")
ntgcalls_logger.setLevel(logging.CRITICAL)
ntgcalls_logger.propagate = False


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
