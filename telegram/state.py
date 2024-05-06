from enum import Enum
from typing import Any
from pydantic import BaseModel


class DialogueTy(Enum):
    Nothing = 0
    MugRename = 1


class Dialogue(BaseModel):
    ty: DialogueTy = DialogueTy.Nothing
    callback: Any = None


class Dialogues(BaseModel):
    items: dict[int, Dialogue] = {}

    def set(self, chat_id: int, ty: DialogueTy, callback: Any = None) -> None:
        self.items[chat_id] = Dialogue(ty=ty, callback=callback)

    def answer(self, chat_id: int, text, message):
        if chat_id not in self.items.keys():
            return None
        v = self.items[chat_id]
        if v.ty == DialogueTy.Nothing:
            return None
        v.ty = DialogueTy.Nothing
        return v.callback(text, message)


CURRENT_DIALOGUE = Dialogues()

from .tgcore import dispatcher as dp
from aiogram.types import Message


@dp.message(lambda m: not m.text.startswith("/"))
async def dialogue_handler(message: Message) -> None:
    global CURRENT_DIALOGUE
    if message.text is not None and not message.text.startswith("/"):
        v = CURRENT_DIALOGUE.answer(message.chat.id, message.text, message)
        if v is not None:
            await v
