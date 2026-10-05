import os

from dotenv import load_dotenv
from telebot.async_telebot import AsyncTeleBot

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = AsyncTeleBot(BOT_TOKEN)

async def notification(user_id: int, message: str):

  return await bot.send_message(
    chat_id=user_id,
    text=message,
    parse_mode="HTML"
  )