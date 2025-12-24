# Authored By Certified Coders © 2025

import os
import json
import shutil
import zipfile
import asyncio
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from Tune import app
from config import LOGGER_ID, OWNER_ID
from Tune.logging import LOGGER
from Tune.core.dir import BACKUP_DIR
from Tune.core.mongo import mongodb
from Tune.utils.decorators.language import language_no_delete
from strings import get_string

TEMP_DIR = os.path.join(BACKUP_DIR, "tmp")

async def _dump_collection(collection, path: str):
    data = []
    async for doc in collection.find({}):
        doc_dict = dict(doc)
        doc_dict.pop("_id", None)
        for key, value in doc_dict.items():
            if isinstance(value, datetime):
                doc_dict[key] = value.isoformat()
        data.append(doc_dict)
    if data:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

async def _create_backup_zip() -> str:
    LOGGER(__name__).info("🗂️ Starting backup process for all collections…")

    collections = await mongodb.list_collection_names()

    for fname in os.listdir(BACKUP_DIR):
        fpath = os.path.join(BACKUP_DIR, fname)
        if os.path.isfile(fpath) and fname.endswith(".zip"):
            try:
                os.remove(fpath)
            except OSError:
                pass

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)

    tasks = [
        _dump_collection(mongodb[coll], os.path.join(TEMP_DIR, f"{coll}.json"))
        for coll in collections
    ]
    await asyncio.gather(*tasks)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"Tune_Backup_{timestamp}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_name)

    LOGGER(__name__).info(f"📦 Creating backup archive: {zip_name}")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(TEMP_DIR):
            for file in files:
                fp = os.path.join(root, file)
                arc = os.path.join("Tune", os.path.relpath(fp, TEMP_DIR))
                zf.write(fp, arc)

    shutil.rmtree(TEMP_DIR)
    return zip_path

async def _send_backup(zip_path: str, chat_id: int, caption: str):
    await app.send_document(chat_id=chat_id, document=zip_path, caption=caption)
    if os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except OSError:
            pass

@app.on_message(filters.command("backup") & filters.user(OWNER_ID))
@language_no_delete
async def manual_backup(client: Client, message: Message, _):
    processing = await message.reply_text(_["backup_1"])
    try:
        zip_path = await _create_backup_zip()
        caption = _["backup_2"].format(os.path.basename(zip_path))
        await _send_backup(zip_path, message.chat.id, caption)
        await processing.delete()
    except Exception as e:
        await processing.edit_text(_["backup_3"].format(str(e)))
        LOGGER(__name__).error(f"Manual backup failed: {e}")

async def daily_backup_task():
    while True:
        now = datetime.now()
        target = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        await asyncio.sleep((target - now).total_seconds())
        try:
            zip_path = await _create_backup_zip()
            _ = get_string("en")
            caption = _["backup_4"]
            await _send_backup(zip_path, LOGGER_ID, caption)
            LOGGER(__name__).info("Daily backup sent to LOGGER_ID.")
        except Exception as e:
            LOGGER(__name__).error(f"Daily backup failed: {e}")

asyncio.create_task(daily_backup_task())
