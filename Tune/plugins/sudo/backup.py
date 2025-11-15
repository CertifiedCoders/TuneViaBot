# Authored By Certified Coders © 2025

import os
import json
import shutil
import zipfile
import asyncio
import re
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import Message
from Tune import app
from config import MONGO_DB_URI, LOGGER_ID, OWNER_ID
from Tune.logging import LOGGER

BACKUP_TEMP = "Tune_backup_temp"
BACKUP_DIR = "Tunebackup"
DOCS_PER_BATCH = 10000

def safe_name(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>| ]+", "_", name)

async def _dump_collection(collection, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n")
        first = True
        batch = []
        async for doc in collection.find({}):
            doc.pop("_id", None)
            batch.append(doc)
            if len(batch) >= DOCS_PER_BATCH:
                for d in batch:
                    if not first:
                        f.write(",\n")
                    json.dump(d, f, ensure_ascii=False, indent=2, default=str)
                    first = False
                batch.clear()
        for d in batch:
            if not first:
                f.write(",\n")
            json.dump(d, f, ensure_ascii=False, indent=2, default=str)
            first = False
        f.write("\n]\n")

async def _create_backup_zip() -> str:
    LOGGER(__name__).info("🗂️ Starting backup process for all databases and collections…")
    client = AsyncIOMotorClient(MONGO_DB_URI)
    if os.path.exists(BACKUP_DIR):
        for file in os.listdir(BACKUP_DIR):
            if file.endswith(".zip"):
                os.remove(os.path.join(BACKUP_DIR, file))
    else:
        os.makedirs(BACKUP_DIR)
    if os.path.exists(BACKUP_TEMP):
        shutil.rmtree(BACKUP_TEMP)
    os.makedirs(BACKUP_TEMP)
    db_names = await client.list_database_names()
    tasks = []
    for db_name in db_names:
        db = client[db_name]
        collections = await db.list_collection_names()
        if not collections:
            continue  # Skip databases with no collections
        for coll in collections:
            path = os.path.join(BACKUP_TEMP, safe_name(db_name), f"{safe_name(coll)}.json")
            tasks.append(_dump_collection(db[coll], path))
    await asyncio.gather(*tasks)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"Tune_Backup_{timestamp}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_name)
    LOGGER(__name__).info(f"📦 Creating backup archive: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(BACKUP_TEMP):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, BACKUP_TEMP)
                zf.write(file_path, arcname)
    LOGGER(__name__).info("🧹 Cleaning temporary backup directory…")
    shutil.rmtree(BACKUP_TEMP)
    return zip_path

async def _send_backup(zip_path: str, chat_id: int, caption: str):
    await app.send_document(
        chat_id=chat_id,
        document=zip_path,
        caption=caption
    )


@app.on_message(filters.command("backup") & filters.user(OWNER_ID))
async def manual_backup(_: Client, message: Message):
    processing = await message.reply_text(
        "🔐 **Starting Backup…**\n"
        "__Please wait while we securely export your databases.__ 🚀"
    )
    try:
        zip_path = await _create_backup_zip()
        caption = (
            "✅ **Backup Successfully Completed!**\n"
            "__Your full MongoDB databases have been safely exported.__ 📁✨\n\n"
            f"**File:** `{os.path.basename(zip_path)}`"
        )
        await _send_backup(zip_path, message.chat.id, caption)
        await processing.delete()
    except Exception as e:
        await processing.edit_text(
            "❌ **Backup Failed!**\n"
            "__Something went wrong during the export process.__\n\n"
            f"**Error:** `{e}`"
        )
        LOGGER(__name__).error(f"⚠️ Manual backup failed: {e}")

async def daily_backup_task():
    while True:
        now = datetime.now()
        target = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_time = (target - now).total_seconds()
        await asyncio.sleep(wait_time)
        try:
            zip_path = await _create_backup_zip()
            caption = (
                "🕛 **Daily Backup — 12:00 AM IST**\n"
                "__Your automatic full databases backup is ready.__ 🔒📦\n\n"
                f"**File:** `{os.path.basename(zip_path)}`"
            )
            await _send_backup(zip_path, LOGGER_ID, caption)
            LOGGER(__name__).info("📤 Daily backup successfully sent to LOGGER_ID.")
        except Exception as e:
            LOGGER(__name__).error(f"⚠️ Daily backup failed: {e}")


asyncio.create_task(daily_backup_task())