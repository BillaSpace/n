from pyrogram import Client, filters
from pyrogram.handlers import ChatMemberUpdatedHandler
from pyrogram.types import ChatMemberUpdated, Message
from typing import Union, List
import asyncio

from AnonXMusic import app

infovc_enabled = True

def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

@app.on_message(command(["infovc"]))
async def toggle_infovc(_, message: Message):
    global infovc_enabled
    if len(message.command) > 1:
        state = message.command[1].lower()
        if state == "on":
            infovc_enabled = True
            await message.reply("Voice chat join notifications are now enabled.")
        elif state == "off":
            infovc_enabled = False
            await message.reply("Voice chat join notifications are now disabled.")
        else:
            await message.reply("Usage: /infovc on or /infovc off")
    else:
        await message.reply("Usage: /infovc on or /infovc off")

async def user_joined_voice_chat(client: Client, chat_member_updated: ChatMemberUpdated):
    global infovc_enabled

    try:
        if not infovc_enabled:
            return

        chat = chat_member_updated.chat
        user = chat_member_updated.new_chat_member.user
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status

        if old_status in ["left", "kicked"] and new_status in ["member", "administrator", "owner"]:
            # Determine the role
            role = "Joined a voice chat"
            if new_status == "administrator":
                role = "Administrator joined The voice chat"
            elif new_status == "owner":
                role = "Owner joined The voice chat"

            text = (
                f"#JoinVoiceChat\n"
                f"Name: {user.mention}\n"
                f"ID: {user.id}\n"
                f"Action: {role}"
            )

            await client.send_message(chat.id, text)

    except Exception as e:
        print(f"Error in user_joined_voice_chat: {e}\nDetails: {chat_member_updated}")

# Register handler
app.add_handler(ChatMemberUpdatedHandler(user_joined_voice_chat))