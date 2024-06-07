from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from models.config import POSTER_PATH, get_config
from aiogram.types import FSInputFile

BOT = Bot(
    token=get_config().bot_token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

POSTER_IMG = FSInputFile(POSTER_PATH)

dispatcher: Dispatcher = Dispatcher()
