from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from models.config import get_config

BOT = Bot(
    token=get_config().bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dispatcher: Dispatcher = Dispatcher()
