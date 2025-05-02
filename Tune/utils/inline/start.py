from pyrogram.types import InlineKeyboardButton
import config
from Tune import app


def start_panel(_):
    return [[InlineKeyboardButton(text=_["S_B_4"], url=config.SUPPORT_CHANNEL)]]


def private_panel(_):
    return [
        [
            InlineKeyboardButton(
                text=_["S_B_1"],
                url=f"https://t.me/{app.username}?startgroup=true",
            )
        ],
        [
            InlineKeyboardButton(text=_["S_B_7"], user_id=config.OWNER_ID),
            InlineKeyboardButton(text=_["S_B_4"], url=config.SUPPORT_CHAT),
        ],
        [
            InlineKeyboardButton(text=_["S_B_3"], callback_data="open_help"),
        ],
    ]
