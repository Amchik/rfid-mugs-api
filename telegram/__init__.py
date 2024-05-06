from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from .tgcore import BOT, dispatcher

from .commands import dp


async def start_bot():
    global BOT
    dispatcher.include_router(dp)
    await dispatcher.start_polling(BOT)
