from pyrogram import filters

from Tune.utils.admin_check import admin_check

USE_AS_BOT = True


def owner_filter_func(filt, client, message):
    if USE_AS_BOT:
        return not message.edit_date
    else:
        return bool(
            message.from_user and message.from_user.is_self and not message.edit_date
        )


owner_filter = filters.create(func=owner_filter_func, name="OwnerFilter")


async def admin_filter_f(filt, client, message):
    return not message.edit_date and await admin_check(message)


admin_filter = filters.create(func=admin_filter_f, name="AdminFilter")
