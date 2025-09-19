import os
from Tune.logging import LOGGER

BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
CACHE_DIR = os.path.join(BASE_DIR, "cache")

def dirr():
    for file in os.listdir():
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            os.remove(file)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    LOGGER(__name__).info("Directories Updated.")
