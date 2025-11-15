# Authored By Certified Coders ©

import os
import json
import shutil
import zipfile
import asyncio
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import Message
from Tune import app
from config import MONGO_DB_URI, LOGGER_ID, OWNER_ID
from Tune.logging import LOGGER

BACKUP_ROOT = "Tune"
DB_NAME = AsyncIOMotorClient(MONGO_DB_URI).get_database().name


async def _dump_collection(collection, path: str):
    data = []
    async for doc in collection.find({}):
        doc.pop("_id", None)
        data.append(doc)
    if data:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


async def _create_backup_zip() -> str:
    client = AsyncIOMotorClient(MONGO_DB_URI)
    db = client[DB_NAME]
    collections = await db.list_collection_names()

    if os.path.exists(BACKUP_ROOT):
        shutil.rmtree(BACKUP_ROOT)
    os.makedirs(BACKUP_ROOT)

    tasks = [
        _dump_collection(db[coll], f"{BACKUP_ROOT}/{coll}.json")
        for coll in collections
    ]
    await asyncio.gather(*tasks)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"Tune_Backup_{timestamp}.zip"
    
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(BACKUP_ROOT):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, ".")
                zf.write(file_path, arcname)

    shutil.rmtree(BACKUP_ROOT)
    return zip_name


async def _send_backup(zip_path: str, chat_id: int, caption: str):
    await app.send_document(
        chat_id=chat_id,
        document=zip_path,
        caption=caption,
        progress=True,
        progress_args=("🔄 **Processing backup… Please wait**",)
    )
    if os.path.exists(zip_path):
        os.remove(zip_path)


@app.on_message(filters.command("backup") & filters.user(OWNER_ID))
async def manual_backup(_: Client, message: Message):
    processing = await message.reply_text(
        "**Processing Backup…**\n"
        "_Please wait while we secure your data_"
    )
    
    try:
        zip_path = await _create_backup_zip()
        caption = (
            "✔️ **Backup Completed**\n"
            "_Your full MongoDB database has been backed up_\n\n"
            f"`{os.path.basename(zip_path)}`"
        )
        await _send_backup(zip_path, message.chat.id, caption)
        await processing.delete()
    except Exception as e:
        await processing.edit_text(f"**Backup Failed**\n`{e}`")
        LOGGER(__name__).error(f"Manual backup failed: {e}")


async def daily_backup_task():
    while True:
        now = datetime.now()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= target:
            target += asyncio.timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())

        try:
            zip_path = await _create_backup_zip()
            caption = (
                "**Daily Backup (12:00 AM IST)**\n"
                "_Full database dump completed automatically_\n\n"
                f"`{os.path.basename(zip_path)}`"
            )
            await _send_backup(zip_path, LOGGER_ID, caption)
            LOGGER(__name__).info("Daily backup sent to LOGGER_ID")
        except Exception as e:
            LOGGER(__name__).error(f"Daily backup failed: {e}")


# Start daily backup scheduler
asyncio.create_task(daily_backup_task())