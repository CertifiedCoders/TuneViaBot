# Authored By Certified Coders © 2025

import random
from typing import Dict, List, Optional, Union

from Tune import userbot
from Tune.core.mongo import mongodb
from Tune.utils.exceptions import AssistantErr

authdb = mongodb.adminauth
authuserdb = mongodb.authuser
autoenddb = mongodb.autoend
assdb = mongodb.assistants
blacklist_chatdb = mongodb.blacklistChat
blockeddb = mongodb.blockedusers
chatsdb = mongodb.chats
channeldb = mongodb.cplaymode
countdb = mongodb.upcount
gbansdb = mongodb.gban
langdb = mongodb.language
onoffdb = mongodb.onoffper
playmodedb = mongodb.playmode
playtypedb = mongodb.playtypedb
skipdb = mongodb.skipmode
sudoersdb = mongodb.sudoers
usersdb = mongodb.tgusersdb
antispamdb = mongodb.antispam
antispamblockeddb = mongodb.antispamblocked

active = []
activevideo = []
assistantdict = {}
autoend = {}
count = {}
channelconnect = {}
langm = {}
loop = {}
maintenance = []
nonadmin = {}
pause = {}
playmode = {}
playtype = {}
skipmode = {}
mute = {}


async def get_assistant_number(chat_id: int) -> Optional[str]:
    return assistantdict.get(chat_id)


async def get_client(assistant: int):
    assistant_index = int(assistant)
    client = userbot.get_assistant(assistant_index)
    if client is None:
        assistants_list = userbot.get_assistants_list()
        if assistants_list:
            return assistants_list[0]
    return client


async def set_assistant_new(chat_id, number):
    number = int(number)
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": number}},
        upsert=True,
    )


async def _set_assistant_in_db(chat_id, assistant):
    assistantdict[chat_id] = assistant
    await assdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": assistant}},
        upsert=True,
    )


async def set_assistant(chat_id):
    from Tune.core.userbot import assistants
    ran_assistant = random.choice(assistants)
    await _set_assistant_in_db(chat_id, ran_assistant)
    return await get_client(ran_assistant)


async def set_calls_assistant(chat_id):
    from Tune.core.userbot import assistants
    ran_assistant = random.choice(assistants)
    await _set_assistant_in_db(chat_id, ran_assistant)
    return ran_assistant


async def get_assistant(chat_id: int):
    from Tune.core.userbot import assistants
    assistant = assistantdict.get(chat_id)
    if assistant and assistant in assistants:
        return await get_client(assistant)
    dbassistant = await assdb.find_one({"chat_id": chat_id})
    if dbassistant:
        got_assis = dbassistant["assistant"]
        if got_assis in assistants:
            assistantdict[chat_id] = got_assis
            return await get_client(got_assis)
    return await set_assistant(chat_id)


async def group_assistant(self, chat_id: int):
    from Tune.core.userbot import assistants
    assistant = assistantdict.get(chat_id)
    if not assistant:
        dbassistant = await assdb.find_one({"chat_id": chat_id})
        if dbassistant and dbassistant["assistant"] in assistants:
            assis = dbassistant["assistant"]
            assistantdict[chat_id] = assis
        else:
            assis = await set_calls_assistant(chat_id)
    elif assistant in assistants:
        assis = assistant
    else:
        assis = await set_calls_assistant(chat_id)
    result = None
    try:
        assis_int = int(assis)
        if hasattr(self, 'assistants_list') and self.assistants_list:
            idx = assis_int - 1
            if 0 <= idx < len(self.assistants_list):
                candidate = self.assistants_list[idx]
                if candidate is not None:
                    result = candidate
    except (ValueError, AttributeError, IndexError):
        pass
    if result is None:
        if hasattr(self, 'assistants_list') and self.assistants_list:
            available = [a for a in self.assistants_list if a is not None]
            if available:
                result = available[0]
        if result is None:
            assistants_attrs = [self.one, self.two, self.three, self.four, self.five]
            available = [a for a in assistants_attrs if a]
            if available:
                result = available[0]
            else:
                raise AssistantErr("No active assistant available.")
    return result


async def is_skipmode(chat_id: int) -> bool:
    mode = skipmode.get(chat_id)
    if mode is not None:
        return mode
    user = await skipdb.find_one({"chat_id": chat_id})
    skipmode[chat_id] = user is None
    return skipmode[chat_id]


async def skip_on(chat_id: int):
    skipmode[chat_id] = True
    user = await skipdb.find_one({"chat_id": chat_id})
    if user:
        return await skipdb.delete_one({"chat_id": chat_id})


async def skip_off(chat_id: int):
    skipmode[chat_id] = False
    user = await skipdb.find_one({"chat_id": chat_id})
    if not user:
        return await skipdb.insert_one({"chat_id": chat_id})


async def get_upvote_count(chat_id: int) -> int:
    mode = count.get(chat_id)
    if mode is not None:
        return mode
    mode = await countdb.find_one({"chat_id": chat_id})
    if not mode:
        return 5
    count[chat_id] = mode["mode"]
    return mode["mode"]


async def set_upvotes(chat_id: int, mode: int):
    count[chat_id] = mode
    await countdb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def is_autoend() -> bool:
    user = await autoenddb.find_one({"chat_id": 1234})
    return user is not None


async def autoend_on():
    await autoenddb.insert_one({"chat_id": 1234})


async def autoend_off():
    await autoenddb.delete_one({"chat_id": 1234})


async def get_loop(chat_id: int) -> int:
    return loop.get(chat_id, 0)


async def set_loop(chat_id: int, mode: int):
    loop[chat_id] = mode


async def get_cmode(chat_id: int) -> Optional[int]:
    mode = channelconnect.get(chat_id)
    if mode is not None:
        return mode
    mode = await channeldb.find_one({"chat_id": chat_id})
    if not mode:
        return None
    channelconnect[chat_id] = mode["mode"]
    return mode["mode"]


async def set_cmode(chat_id: int, mode: int):
    channelconnect[chat_id] = mode
    await channeldb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playtype(chat_id: int) -> str:
    mode = playtype.get(chat_id)
    if mode:
        return mode
    mode = await playtypedb.find_one({"chat_id": chat_id})
    if not mode:
        playtype[chat_id] = "Everyone"
        return "Everyone"
    playtype[chat_id] = mode["mode"]
    return mode["mode"]


async def set_playtype(chat_id: int, mode: str):
    playtype[chat_id] = mode
    await playtypedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_playmode(chat_id: int) -> str:
    mode = playmode.get(chat_id)
    if mode:
        return mode
    mode = await playmodedb.find_one({"chat_id": chat_id})
    if not mode:
        playmode[chat_id] = "Direct"
        return "Direct"
    playmode[chat_id] = mode["mode"]
    return mode["mode"]


async def set_playmode(chat_id: int, mode: str):
    playmode[chat_id] = mode
    await playmodedb.update_one(
        {"chat_id": chat_id}, {"$set": {"mode": mode}}, upsert=True
    )


async def get_lang(chat_id: int) -> str:
    mode = langm.get(chat_id)
    if mode:
        return mode
    lang = await langdb.find_one({"chat_id": chat_id})
    if not lang:
        langm[chat_id] = "en"
        return "en"
    langm[chat_id] = lang["lang"]
    return lang["lang"]


async def set_lang(chat_id: int, lang: str):
    langm[chat_id] = lang
    await langdb.update_one({"chat_id": chat_id}, {"$set": {"lang": lang}}, upsert=True)


async def is_music_playing(chat_id: int) -> bool:
    return bool(pause.get(chat_id))


async def music_on(chat_id: int):
    pause[chat_id] = True


async def music_off(chat_id: int):
    pause[chat_id] = False


async def is_muted(chat_id: int) -> bool:
    return bool(mute.get(chat_id))


async def get_active_chats() -> List[int]:
    return active


async def is_active_chat(chat_id: int) -> bool:
    return chat_id in active


async def add_active_chat(chat_id: int):
    if chat_id not in active:
        active.append(chat_id)


async def remove_active_chat(chat_id: int):
    if chat_id in active:
        active.remove(chat_id)


async def get_active_video_chats() -> List[int]:
    return activevideo


async def is_active_video_chat(chat_id: int) -> bool:
    return chat_id in activevideo


async def add_active_video_chat(chat_id: int):
    if chat_id not in activevideo:
        activevideo.append(chat_id)


async def remove_active_video_chat(chat_id: int):
    if chat_id in activevideo:
        activevideo.remove(chat_id)


async def check_nonadmin_chat(chat_id: int) -> bool:
    user = await authdb.find_one({"chat_id": chat_id})
    return user is not None


async def is_nonadmin_chat(chat_id: int) -> bool:
    mode = nonadmin.get(chat_id)
    if mode is not None:
        return mode
    user = await authdb.find_one({"chat_id": chat_id})
    nonadmin[chat_id] = user is not None
    return nonadmin[chat_id]


async def add_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = True
    if not await check_nonadmin_chat(chat_id):
        return await authdb.insert_one({"chat_id": chat_id})


async def remove_nonadmin_chat(chat_id: int):
    nonadmin[chat_id] = False
    if await check_nonadmin_chat(chat_id):
        return await authdb.delete_one({"chat_id": chat_id})


async def is_on_off(on_off: int) -> bool:
    onoff = await onoffdb.find_one({"on_off": on_off})
    return onoff is not None


async def add_on(on_off: int):
    if not await is_on_off(on_off):
        return await onoffdb.insert_one({"on_off": on_off})


async def add_off(on_off: int):
    if await is_on_off(on_off):
        return await onoffdb.delete_one({"on_off": on_off})


async def is_maintenance():
    if not maintenance:
        get = await onoffdb.find_one({"on_off": 1})
        maintenance.clear()
        maintenance.append(2 if not get else 1)
        return not get
    return 1 not in maintenance


async def maintenance_off():
    maintenance.clear()
    maintenance.append(2)
    if await is_on_off(1):
        return await onoffdb.delete_one({"on_off": 1})


async def maintenance_on():
    maintenance.clear()
    maintenance.append(1)
    if not await is_on_off(1):
        return await onoffdb.insert_one({"on_off": 1})


async def is_served_user(user_id: int) -> bool:
    user = await usersdb.find_one({"user_id": user_id})
    return user is not None


async def get_served_users() -> List[dict]:
    users_list = []
    async for user in usersdb.find({"user_id": {"$gt": 0}}):
        users_list.append(user)
    return users_list


async def add_served_user(user_id: int):
    if not await is_served_user(user_id):
        return await usersdb.insert_one({"user_id": user_id})


async def get_served_chats() -> List[dict]:
    chats_list = []
    async for chat in chatsdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat)
    return chats_list


async def is_served_chat(chat_id: int) -> bool:
    chat = await chatsdb.find_one({"chat_id": chat_id})
    return chat is not None


async def add_served_chat(chat_id: int):
    if not await is_served_chat(chat_id):
        return await chatsdb.insert_one({"chat_id": chat_id})


async def remove_served_chat(chat_id: int):
    if await is_served_chat(chat_id):
        await chatsdb.delete_one({"chat_id": chat_id})


async def remove_served_user(user_id: int):
    if await is_served_user(user_id):
        await usersdb.delete_one({"user_id": user_id})


async def blacklisted_chats() -> List[int]:
    chats_list = []
    async for chat in blacklist_chatdb.find({"chat_id": {"$lt": 0}}):
        chats_list.append(chat["chat_id"])
    return chats_list


async def blacklist_chat(chat_id: int) -> bool:
    if not await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.insert_one({"chat_id": chat_id})
        return True
    return False


async def whitelist_chat(chat_id: int) -> bool:
    if await blacklist_chatdb.find_one({"chat_id": chat_id}):
        await blacklist_chatdb.delete_one({"chat_id": chat_id})
        return True
    return False


async def _get_authusers(chat_id: int) -> Dict[str, dict]:
    _notes = await authuserdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes["notes"]


async def get_authuser_names(chat_id: int) -> List[str]:
    return list(await _get_authusers(chat_id))


async def get_authuser(chat_id: int, name: str) -> Union[bool, dict]:
    _notes = await _get_authusers(chat_id)
    return _notes.get(name, False)


async def save_authuser(chat_id: int, name: str, note: dict):
    _notes = await _get_authusers(chat_id)
    _notes[name] = note
    await authuserdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )


async def delete_authuser(chat_id: int, name: str) -> bool:
    notesd = await _get_authusers(chat_id)
    if name in notesd:
        del notesd[name]
        await authuserdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False


async def get_gbanned() -> List[int]:
    results = []
    async for user in gbansdb.find({"user_id": {"$gt": 0}}):
        results.append(user["user_id"])
    return results


async def is_gbanned_user(user_id: int) -> bool:
    user = await gbansdb.find_one({"user_id": user_id})
    return user is not None


async def add_gban_user(user_id: int):
    if not await is_gbanned_user(user_id):
        return await gbansdb.insert_one({"user_id": user_id})


async def remove_gban_user(user_id: int):
    if await is_gbanned_user(user_id):
        return await gbansdb.delete_one({"user_id": user_id})


async def get_sudoers() -> List[int]:
    sudoers = await sudoersdb.find_one({"sudo": "sudo"})
    if not sudoers:
        return []
    return sudoers["sudoers"]


async def add_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    sudoers.append(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def remove_sudo(user_id: int) -> bool:
    sudoers = await get_sudoers()
    if user_id not in sudoers:
        return False
    sudoers.remove(user_id)
    await sudoersdb.update_one(
        {"sudo": "sudo"}, {"$set": {"sudoers": sudoers}}, upsert=True
    )
    return True


async def get_banned_users() -> List[int]:
    results = []
    async for user in blockeddb.find({"user_id": {"$gt": 0}}):
        results.append(user["user_id"])
    return results


async def get_banned_count() -> int:
    return await blockeddb.count_documents({"user_id": {"$gt": 0}})


async def is_banned_user(user_id: int) -> bool:
    user = await blockeddb.find_one({"user_id": user_id})
    return user is not None


async def add_banned_user(user_id: int):
    if not await is_banned_user(user_id):
        return await blockeddb.insert_one({"user_id": user_id})


async def remove_banned_user(user_id: int):
    if await is_banned_user(user_id):
        return await blockeddb.delete_one({"user_id": user_id})


async def is_antispam_enabled() -> bool:
    config = await antispamdb.find_one({"config": "antispam"})
    if not config:
        await antispamdb.insert_one({"config": "antispam", "enabled": True})
        return True
    return config.get("enabled", True)


async def antispam_on():
    await antispamdb.update_one(
        {"config": "antispam"}, {"$set": {"enabled": True}}, upsert=True
    )


async def antispam_off():
    await antispamdb.update_one(
        {"config": "antispam"}, {"$set": {"enabled": False}}, upsert=True
    )


async def is_spam_blocked(user_id: int) -> bool:
    user_id = int(user_id)
    user = await antispamblockeddb.find_one({"user_id": user_id})
    if not user:
        user = await antispamblockeddb.find_one({"user_id": str(user_id)})
    return bool(user)


async def add_spam_blocked_user(user_id: int, command_count: int, time_window: int):
    user_id = int(user_id)
    await antispamblockeddb.delete_one({"user_id": str(user_id)})
    await antispamblockeddb.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "command_count": command_count,
                "time_window": time_window,
            }
        },
        upsert=True,
    )


async def remove_spam_blocked_user(user_id: int) -> bool:
    user_id = int(user_id)
    result = await antispamblockeddb.delete_one({"user_id": user_id})
    if result.deleted_count == 0:
        result = await antispamblockeddb.delete_one({"user_id": str(user_id)})
    return result.deleted_count > 0


async def get_spam_blocked_users() -> List[int]:
    results = []
    async for user in antispamblockeddb.find({}):
        user_id = user.get("user_id")
        if user_id:
            try:
                results.append(int(user_id))
            except (ValueError, TypeError):
                continue
    return results
