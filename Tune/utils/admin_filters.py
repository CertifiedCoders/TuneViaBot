# Authored By Certified Coders © 2025
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery
from Tune.utils.admin_check import is_admin, is_group_owner
from Tune.misc import SUDOERS
from config import OWNER_ID


def _extract_message(obj: Message | CallbackQuery) -> Message:
    return obj.message if isinstance(obj, CallbackQuery) else obj


def _is_edited_message(msg: Message) -> bool:
    return bool(getattr(msg, "edit_date", False))


def sudo_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    msg = _extract_message(obj)
    if _is_edited_message(msg):
        return False
    return bool(
        (msg.from_user and msg.from_user.id in SUDOERS)
        or (msg.sender_chat and msg.sender_chat.id in SUDOERS)
    )

sudo_filter = filters.create(func=sudo_filter_func, name="SudoUsersFilter")


async def admin_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    msg = _extract_message(obj)
    if _is_edited_message(msg):
        return False
    return await is_admin(msg)

admin_filter = filters.create(func=admin_filter_func, name="AdminFilter")


async def group_owner_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    msg = _extract_message(obj)
    if _is_edited_message(msg):
        return False
    return await is_group_owner(msg)

group_owner_filter = filters.create(func=group_owner_filter_func, name="GroupOwnerFilter")


def bot_owner_filter_func(_, __, obj: Message | CallbackQuery) -> bool:
    msg = _extract_message(obj)
    if _is_edited_message(msg):
        return False
    return msg.from_user and msg.from_user.id == OWNER_ID

dev_filter = filters.create(func=bot_owner_filter_func, name="BotOwnerFilter")
