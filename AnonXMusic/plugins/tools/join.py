from pyrogram import Client, filters
from pyrogram.handlers import ChatMemberUpdatedHandler
from pyrogram.types import ChatMemberUpdated, Message
from typing import Union, List
import asyncio

from AnonXMusic import app

# Default state for /infovc
infovc_enabled = True  # Default to always true

# Command decorator
def command(commands: Union[str, List[str]]):
    return filters.command(commands, prefixes=["/"])

# Command to toggle /infovc on/off
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

# Handler to notify when users join voice chats
async def user_joined_voice_chat(client: Client, chat_member_updated: ChatMemberUpdated):
    global infovc_enabled

    try:
        # Check if notifications are enabled
        if not infovc_enabled:
            return

        chat = chat_member_updated.chat
        user = chat_member_updated.new_chat_member.user
        chat_id = chat.id

        # Debug: Print event details
        print(f"ChatMemberUpdated event: {chat_member_updated}")

        # Check if the event is related to joining a voice chat
        if (
            not (chat_member_updated.old_chat_member and chat_member_updated.old_chat_member.is_participant)
            and (chat_member_updated.new_chat_member and chat_member_updated.new_chat_member.is_participant)
        ):
            # Construct the message
            text = (
                f"#JoinVoiceChat\n"
                f"Name: {user.mention}\n"
                f"ID: {user.id}\n"
                f"Action: Joined a voice chat"
            )

            # Debug: Print the message before sending
            print(f"Message to send: {text}")

            # Send the message
            await client.send_message(chat_id, text)
    except Exception as e:
        # Log any errors with more details
        print(f"Error in user_joined_voice_chat: {e}\nDetails: {chat_member_updated}")

# Add the handler for chat member updates
app.add_handler(ChatMemberUpdatedHandler(user_joined_voice_chat))
