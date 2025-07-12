import asyncio

from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils import get_readable_time
from AnonXMusic.utils.database import (
    add_banned_user,
    get_banned_count,
    get_banned_users,
    get_served_chats,
    is_banned_user,
    remove_banned_user,
)
from AnonXMusic.utils.decorators.language import language
from AnonXMusic.utils.extraction import extract_user
from config import BANNED_USERS


@app.on_message(filters.command(["gban", "globalban"]) & SUDOERS)
@language
async def global_ban(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    try:
        user = await extract_user(message)
    except Exception:
        return await message.reply_text(_["general_1"])

    if user.id == message.from_user.id:
        return await message.reply_text(_["gban_1"])
    if user.id == app.id:
        return await message.reply_text(_["gban_2"])
    if user.id in SUDOERS:
        return await message.reply_text(_["gban_3"])
    if await is_banned_user(user.id):
        return await message.reply_text(_["gban_4"].format(user.mention))

    BANNED_USERS.add(user.id)

    chats = await get_served_chats()
    served_chats = [int(chat) for chat in chats]

    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(_["gban_5"].format(user.mention, time_expected))

    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.ban_chat_member(chat_id, user.id)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception:
            continue

        try:
            async for msg in app.search_messages(chat_id, from_user=user.id):
                try:
                    await app.delete_messages(chat_id, msg.id)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except Exception:
                    continue
        except Exception:
            pass

        number_of_chats += 1

    await add_banned_user(user.id)

    await message.reply_text(
        _["gban_6"].format(
            app.mention,
            message.chat.title,
            message.chat.id,
            user.mention,
            user.id,
            message.from_user.mention,
            number_of_chats,
        )
    )
    await mystic.delete()


@app.on_message(filters.command(["ungban"]) & SUDOERS)
@language
async def global_unban(client, message: Message, _):
    if not message.reply_to_message and len(message.command) != 2:
        return await message.reply_text(_["general_1"])

    try:
        user = await extract_user(message)
    except Exception:
        return await message.reply_text(_["general_1"])

    if not await is_banned_user(user.id):
        return await message.reply_text(_["gban_7"].format(user.mention))

    BANNED_USERS.discard(user.id)

    chats = await get_served_chats()
    served_chats = [int(chat) for chat in chats]

    time_expected = get_readable_time(len(served_chats))
    mystic = await message.reply_text(_["gban_8"].format(user.mention, time_expected))

    number_of_chats = 0
    for chat_id in served_chats:
        try:
            await app.unban_chat_member(chat_id, user.id)
            number_of_chats += 1
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception:
            continue

    await remove_banned_user(user.id)
    await message.reply_text(_["gban_9"].format(user.mention, number_of_chats))
    await mystic.delete()


@app.on_message(filters.command(["gbannedusers", "gbanlist"]) & SUDOERS)
@language
async def gbanned_list(client, message: Message, _):
    counts = await get_banned_count()
    if counts == 0:
        return await message.reply_text(_["gban_10"])

    mystic = await message.reply_text(_["gban_11"])
    msg = _["gban_12"]
    count = 0

    users = await get_banned_users()
    for user_id in users:
        count += 1
        try:
            user = await app.get_users(user_id)
            mention = user.mention if user.mention else user.first_name
            msg += f"{count}➤ {mention}\n"
        except Exception:
            msg += f"{count}➤ {user_id}\n"

    await mystic.edit_text(msg)


# 👇 Auto-delete messages sent by gbanned users in real time
@app.on_message(filters.group, group=999)
async def delete_gbanned_messages(_, message: Message):
    user = message.from_user
    if not user:
        return
    if await is_banned_user(user.id):
        try:
            await message.delete()
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
        except Exception:
            pass
