import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from AnonXMusic import app
from AnonXMusic.misc import SUDOERS
from AnonXMusic.utils.database import (
    get_served_chats,
    get_served_users,
    get_client,
    get_active_chats,
    get_authuser_names,
)
from AnonXMusic.utils.decorators.language import language
from pyrogram.enums import ChatMembersFilter
from AnonXMusic.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False
BROADCAST_LIMIT = 50  # Number of concurrent messages
FLOOD_SLEEP_THRESHOLD = 200  # Ignore waits longer than this


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def broadcast_message(client, message, _):
    global IS_BROADCASTING
    if IS_BROADCASTING:
        return await message.reply_text("🚀 **A broadcast is already in progress.**")

    IS_BROADCASTING = True
    await message.reply_text("🚀 **Broadcast started...**")

    # Extract message content
    if message.reply_to_message:
        msg_id = message.reply_to_message.id
        chat_id = message.chat.id
        query = None
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        query = message.text.split(None, 1)[1]
        for flag in ["-pin", "-nobot", "-pinloud", "-assistant", "-user"]:
            query = query.replace(flag, "").strip()
        if not query:
            return await message.reply_text(_["broad_8"])

    async def send_messages(chat_list, is_user=False):
        """Send messages concurrently with floodwait handling."""
        sent, pin_count = 0, 0
        semaphore = asyncio.Semaphore(BROADCAST_LIMIT)

        async def send_single(chat_id):
            nonlocal sent, pin_count
            async with semaphore:
                try:
                    if message.reply_to_message:
                        msg = await app.forward_messages(chat_id, chat_id, msg_id)
                    else:
                        msg = await app.send_message(chat_id, text=query)
                    sent += 1

                    # Pinning logic
                    if "-pin" in message.text:
                        await msg.pin(disable_notification=True)
                        pin_count += 1
                    elif "-pinloud" in message.text:
                        await msg.pin(disable_notification=False)
                        pin_count += 1

                except FloodWait as fw:
                    if fw.value > FLOOD_SLEEP_THRESHOLD:
                        return
                    await asyncio.sleep(fw.value)
                except Exception:
                    pass

        await asyncio.gather(*(send_single(chat) for chat in chat_list))
        return sent, pin_count

    # Broadcast to Groups
    sent, pin_count = 0, 0
    if "-nobot" not in message.text:
        chats = [int(chat["chat_id"]) for chat in await get_served_chats()]
        sent, pin_count = await send_messages(chats)
        await message.reply_text(f"✅ **Broadcasted to {sent} groups, pinned in {pin_count} groups.**")

    # Broadcast to Users
    if "-user" in message.text:
        users = [int(user["user_id"]) for user in await get_served_users()]
        user_sent, _ = await send_messages(users, is_user=True)
        await message.reply_text(f"✅ **Broadcasted to {user_sent} users.**")

    # Assistant Broadcast
    if "-assistant" in message.text:
        aw = await message.reply_text("⏳ **Broadcasting via assistants...**")
        from AnonXMusic.core.userbot import assistants

        async def send_via_assistants():
            semaphore = asyncio.Semaphore(5)  # Limit concurrent assistant requests
            tasks = []

            async def assistant_broadcast(num):
                async with semaphore:
                    client = await get_client(num)
                    sent = 0
                    try:
                        async for dialog in client.get_dialogs():
                            try:
                                if message.reply_to_message:
                                    await client.forward_messages(dialog.chat.id, chat_id, msg_id)
                                else:
                                    await client.send_message(dialog.chat.id, text=query)
                                sent += 1
                            except FloodWait as fw:
                                if fw.value > FLOOD_SLEEP_THRESHOLD:
                                    return
                                await asyncio.sleep(fw.value)
                            except:
                                pass
                    except:
                        return
                    return f"Assistant {num}: {sent} messages sent\n"

            for num in assistants:
                tasks.append(assistant_broadcast(num))

            results = await asyncio.gather(*tasks)
            return "".join(filter(None, results))

        assist_msg = await send_via_assistants()
        await aw.edit_text(f"🤖 **Assistant Broadcast Summary:**\n{assist_msg}")

    IS_BROADCASTING = False
    await message.reply_text("✅ **Broadcast Completed!** 🚀")


async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if user.privileges.can_manage_video_chats:
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
