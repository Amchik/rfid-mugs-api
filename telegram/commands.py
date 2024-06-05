from time import time
from typing import Optional
from .state import CURRENT_DIALOGUE as diag, DialogueTy
from .tgcore import BOT, POSTER_IMG
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters.callback_data import CallbackData
from models.activation import CURRENT_ACTIVATOR, ActivationThing, RFIDActivation
import re

dp = Router()
# from .tgcore import dispatcher as dp


@dp.message(Command("start"))
async def start(msg: Message) -> None:
    await msg.reply_photo(
        photo=POSTER_IMG,
        caption="<b>Инвентаризация с помощью RFID ☕️</b>\n\n"
        + "Добрый день! Вы попали в сказочную страну, где никто не ворует Вашу кружку ✨\n\nПрисоедениться к студенческому проекту:\n"
        + "💳 Зарегистрироваться: /changecard\n"
        + "📩 Инструкция: /help\n",
    )


@dp.message(Command("help"))
async def help(msg: Message) -> None:
    await msg.reply(
        "<b>📕 Инструкция</b>\n\n"
        + "<b>I Регистрация карты</b>\n"
        + "1. Напишите /changecard\n"
        + "2. Поднесите карту к считывателю, затем нажмите на ПРАВУЮ кнопку\n"
        + "3. Если ничего не происходит, то попробуйте нажать на кнопку ещё раз. Если выдаёт ошибку, обратитесь к @platfoxxx\n\n"
        + "<b>II Регистрация кружек</b>\n"
        + "1. Напишите /newmug\n"
        + "2. Если нужно, измените имя кружки\n"
        + "3. Нажмите кнопку «Подтвердить» в боте\n"
        + "4. Поднесите кружку к считывателю, затем нажмите на ПРАВУЮ кнопку\n\n"
        + "<b>III Переименование/удаление кружек</b>\n"
        + "1. Напишите /mugs\n"
        + "2. Выберете кнопками нужные вам действия\n"
        + "3. Если всё прям совсем печально, напишите @platfoxxx\n\n"
        + "📩 Если что-то прям сломалось, вы можете написать @platfoxxx",
    )


def escapeHTML(s: str) -> str:
    return s.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")


def normalize_mug_name(name: str) -> Optional[str]:
    name = re.sub(r"[^A-Za-zа-яА-ЯёЁ ,.0-9\-]", "", name.strip())
    name = name[:19].strip()
    return name if len(name) > 0 else None


class CancelActivationQuery(CallbackData, prefix="v1+ca"):
    user_id: int


class ChangeMugNameQuery(CallbackData, prefix="v1+cmn"):
    mug_id: int = 0

    def is_new_mug(self):
        return self.mug_id == 0


class CancelDialogueQuery(CallbackData, prefix="v1+cd"):
    pass


class RegisterMugQuery(CallbackData, prefix="v1+rm"):
    name: str


@dp.message(Command("changecard"))
async def changecard(message: Message) -> None:
    global CURRENT_ACTIVATOR
    if not CURRENT_ACTIVATOR.is_outdated():
        df = int(45 + CURRENT_ACTIVATOR.created_at - time()) + 1
        await message.reply(
            f"✋ Считыватель сейчас занят. Подождите ещё <b>{df} секунд</b>."
        )
        return
    m = await message.reply(
        "<b>❯❯❯ Регистрация карты 💳</b>\n\n"
        + "Поднесите свою карту к считывателю и нажмите на правую кнопку",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 Отменить",
                        callback_data=CancelActivationQuery(
                            user_id=message.chat.id
                        ).pack(),
                    )
                ]
            ]
        ),
    )

    telegram_name = message.chat.full_name

    async def callback(act: RFIDActivation):
        global BOT
        await BOT.edit_message_text(
            "<b>❯❯❯ Регистрация карты 💳</b>\n\n"
            + "Карта обновлена. Теперь вы можете зарегистрировать свою кружку используя /newmug",
            act.user_id,
            act.msg_id,
        )
        # NOTE: optimize?
        conn = await get_connection()
        await conn.execute(
            "UPDATE users SET telegram_name = ? WHERE telegram_id = ?",
            [telegram_name, act.user_id],
        )
        await commit_changes()

    CURRENT_ACTIVATOR.set(
        ty=ActivationThing.UpdateCard,
        user_id=message.chat.id,
        msg_id=m.message_id,
        callback=callback,
    )


async def send_newmug_confirmation(msg: Message, mug_name: Optional[str]):
    if not mug_name:
        mug_name = "Кружка"
    await msg.reply(
        "<b>❯❯❯ Регистрация кружки ☕️</b>\n\n"
        + "Вы собираетесь добавить ещё одну кружку как свою.\n"
        + (f"Её название: <b>{escapeHTML(mug_name)}</b>"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✍️ Изменить имя", callback_data=ChangeMugNameQuery().pack()
                    ),
                    InlineKeyboardButton(
                        text="✅ Подтвердить",
                        callback_data=RegisterMugQuery(name=mug_name).pack(),
                    ),
                ]
            ]
        ),
    )


from database import commit_changes, get_connection


@dp.message(Command("newmug"))
async def newmug(msg: Message) -> None:
    conn = await get_connection()
    await conn.execute(
        "select count(1) from users where telegram_id = ?", [msg.chat.id]
    )
    res = (await conn.fetchone())[0]
    if res == 0:
        await msg.reply("❗️ Сначала привяжите свою карту: /changecard")
        return

    mug_name = (
        normalize_mug_name(msg.chat.first_name)
        if msg.chat.first_name is not None
        else "Кружка"
    )
    await send_newmug_confirmation(msg, mug_name)


@dp.callback_query(ChangeMugNameQuery.filter())
async def change_mug_name(query: CallbackQuery, callback_data: ChangeMugNameQuery):
    global diag
    if not callback_data.is_new_mug():
        # TODO:
        return

    async def callback(mug_name: str, msg: Message):
        global diag
        mug_name = normalize_mug_name(mug_name)
        if mug_name is None:
            await msg.reply(
                "❗️ Название кружки должно состоять из русских или английский букв, цифр и некоторых знаков. Попробуйте ещё раз:"
            )
            diag.set(msg.chat.id, DialogueTy.MugRename, callback)
            return
        await send_newmug_confirmation(msg, mug_name)

    await query.message.edit_text(
        "<b>❯❯❯ Регистрация кружки ☕️</b>\n\n" + "Напишите в чат новое имя кружки:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 Отменить", callback_data=CancelDialogueQuery().pack()
                    )
                ]
            ]
        ),
    )

    diag.set(query.message.chat.id, DialogueTy.MugRename, callback)


@dp.callback_query(CancelDialogueQuery.filter())
async def cancel_dialog_query(query: CallbackQuery):
    global diag
    diag.set(query.message.chat.id, DialogueTy.Nothing)
    await query.message.delete()


@dp.callback_query(RegisterMugQuery.filter())
async def register_mug(query: CallbackQuery, callback_data: RegisterMugQuery):
    global CURRENT_ACTIVATOR
    if not CURRENT_ACTIVATOR.is_outdated():
        df = int(45 + CURRENT_ACTIVATOR.created_at - time()) + 1
        await query.message.edit_text(
            f"✋ Считыватель сейчас занят. Подождите ещё <b>{df} секунд</b>.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⏳ Попробовать снова",
                            callback_data=callback_data.pack(),
                        )
                    ]
                ]
            ),
        )
        return
    await query.message.edit_text(
        "<b>❯❯❯ Регистрация кружки 💳</b>\n\n"
        + "Поднесите свою кружку к считывателю и нажмите на правую кнопку\n"
        + f"Название кружки <b>{escapeHTML(callback_data.name)}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚫 Отменить",
                        callback_data=CancelActivationQuery(
                            user_id=query.message.chat.id
                        ).pack(),
                    )
                ]
            ]
        ),
    )

    async def callback(act: RFIDActivation):
        global BOT
        await BOT.edit_message_text(
            "<b>❯❯❯ Регистрация кружки ☕️</b>\n\n"
            + "Кружка зарегистрированна.\n"
            + f"Название кружки: <b>{escapeHTML(callback_data.name)}</b>",
            act.user_id,
            act.msg_id,
        )

    CURRENT_ACTIVATOR.set(
        ty=ActivationThing.CreateMug,
        user_id=query.message.chat.id,
        msg_id=query.message.message_id,
        name=callback_data.name,
        callback=callback,
    )


@dp.callback_query(CancelActivationQuery.filter())
async def kill_message(query: CallbackQuery, callback_data: CancelActivationQuery):
    global CURRENT_ACTIVATOR
    try:
        await query.message.delete()
        if callback_data.user_id == CURRENT_ACTIVATOR.user_id:
            CURRENT_ACTIVATOR.outdate()
    except:
        pass
