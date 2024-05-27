from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from .tgcore import BOT, dispatcher

from .commands import dp as dp_commands
from .mugs_dialogue import dp as dp_mugs


async def start_bot():
    global BOT
    dispatcher.include_router(dp_commands)
    dispatcher.include_router(dp_mugs)
    await dispatcher.start_polling(BOT)
