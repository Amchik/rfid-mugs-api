from datetime import datetime, timedelta
from enum import Enum
from time import time
from typing import Optional

from aiosqlite import Cursor
from pydantic import BaseModel

from telegram.commands import CancelDialogueQuery, escapeHTML, normalize_mug_name
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
import database as db

dp = Router()
# from .tgcore import dispatcher as dp


class MugActionTy(str, Enum):
    VIEW = "v"
    RENAME = "r"
    ASK_DELETE = "a"
    CONFIRM_DELETE = "c"


class MugActionsQuery(CallbackData, prefix="v1+mua"):
    action_ty: MugActionTy
    mug_id: int
    mug_no: int
    current_offset: int


class MugNextPageQuery(CallbackData, prefix="v1+mnp"):
    offset: int


class MugEntry(BaseModel):
    id: int
    name: str
    taker_telegram: Optional[int]
    taker_name: Optional[str]
    last_taken_at: int
    owner_telegram: int


async def get_mug_by_id(con: Cursor, user_id: int, mug_id: int) -> Optional[MugEntry]:
    await con.execute(
        """
        SELECT
            mugs.id,
            mugs.name,
            taker.telegram_id,
            mugs.last_taken_at,
            owner.telegram_id as owner_telegram_id,
            taker.telegram_name
        FROM mugs
            INNER JOIN users AS owner ON owner.id = mugs.owner_id
            LEFT  JOIN users AS taker ON taker.id = mugs.last_taken_by
        WHERE
            mugs.id = ? AND owner.telegram_id = ?
        """,
        [mug_id, user_id],
    )
    row = await con.fetchone()
    if row is None:
        return None
    return MugEntry(
        id=row[0],
        name=row[1],
        taker_telegram=row[2],
        last_taken_at=row[3],
        owner_telegram=row[4],
        taker_name=row[5],
    )


async def get_mugs(con: Cursor, user_id: int, offset: int = 0) -> list[MugEntry]:
    await con.execute(
        """
        SELECT
            mugs.id,
            mugs.name,
            taker.telegram_id,
            mugs.last_taken_at,
            owner.telegram_id as owner_telegram_id,
            taker.telegram_name
        FROM mugs
            INNER JOIN users AS owner ON owner.id = mugs.owner_id
            LEFT  JOIN users AS taker ON taker.id = mugs.last_taken_by
        WHERE
            owner.telegram_id = ?
        LIMIT 5 OFFSET ?
        """,
        [user_id, offset],
    )
    rows = await con.fetchall()
    return list(
        map(
            lambda v: MugEntry(
                id=v[0],
                name=v[1],
                taker_telegram=v[2],
                last_taken_at=v[3],
                owner_telegram=v[4],
                taker_name=v[5],
            ),
            rows,
        )
    )


def format_mug_used_at(mug: MugEntry) -> str:
    dt = datetime(1970, 1, 1) + timedelta(seconds=mug.last_taken_at)
    last_used_time = dt.strftime(r"%d %b %H:%M")
    used_by = "вы"
    if mug.taker_telegram != mug.owner_telegram:
        taker_name = (
            escapeHTML(mug.taker_name)
            if mug.taker_name is not None
            else "другим пользователем"
        )
        used_by = f'<a href="tg://user?id={mug.taker_telegram}">{taker_name}</a>'
    return f"{last_used_time} ({used_by})"


def format_mugs(mugs: list[MugEntry], offset: int = 0) -> str:
    def fmt(v):
        i: int = v[0] + 1 + offset
        v: MugEntry = v[1]
        lst_used_str = (
            "(никогда)" if v.taker_telegram is None else format_mug_used_at(v)
        )
        return (
            f"<b><u>[{i}]</u> {escapeHTML(v.name)}</b>\n"
            + f"<i>Последнее использование: {lst_used_str}</i>\n"
        )

    return "\n".join(map(fmt, enumerate(mugs)))


def get_mugs_buttons(
    mugs: list[MugEntry], offset: int = 0
) -> list[InlineKeyboardButton]:
    buttons = list(
        map(
            lambda v: InlineKeyboardButton(
                text=f"[{v[0]+offset+1}]",
                callback_data=MugActionsQuery(
                    mug_id=v[1].id,
                    current_offset=offset,
                    action_ty=MugActionTy.VIEW,
                    mug_no=v[0] + offset + 1,
                ).pack(),
            ),
            enumerate(mugs),
        )
    )
    if len(buttons) == 5:
        buttons.append(
            InlineKeyboardButton(
                text=f">>>", callback_data=MugNextPageQuery(offset=offset + 5).pack()
            )
        )
    return buttons


@dp.message(Command("mugs"))
async def create_mugs_message(msg: Message) -> None:
    con = await db.get_connection()
    mugs = await get_mugs(con, msg.chat.id)
    if len(mugs) == 0:
        await msg.answer("У вас ещё нет кружек. Можете зарегистрировать одну: /newmug")
        return
    buttons = get_mugs_buttons(mugs)
    await msg.answer(
        f"ℹ️ <b>Ваши кружки:</b>\n\n" + format_mugs(mugs),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[buttons[0:3], buttons[3:6]]),
    )


@dp.callback_query(MugNextPageQuery.filter())
async def mug_next_page_query(query: CallbackQuery, callback_data: MugNextPageQuery):
    offset = callback_data.offset
    con = await db.get_connection()
    mugs = await get_mugs(con, query.message.chat.id, offset)
    if len(mugs) == 0:
        await query.answer("У вас больше нет кружек")
        return
    buttons = get_mugs_buttons(mugs, offset)
    ctrl_buttons = []
    if offset > 0:
        ctrl_buttons = [
            InlineKeyboardButton(
                text="<<<", callback_data=MugNextPageQuery(offset=offset - 5).pack()
            ),
            InlineKeyboardButton(
                text="На первую", callback_data=MugNextPageQuery(offset=0).pack()
            ),
        ]
    await query.message.edit_text(
        f"ℹ️ <b>Ваши кружки:</b>\n\n" + format_mugs(mugs, offset),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[buttons[0:3], buttons[3:6], ctrl_buttons]
        ),
    )


# Я приношу свои глубочайшие извинения тому человеку, что решит прочитать эту функцию
# Её можно рефакторнуть многими путями, ik
@dp.callback_query(MugActionsQuery.filter())
async def mug_action_query(query: CallbackQuery, callback_data: MugActionsQuery):
    act = callback_data.action_ty
    mug_id = callback_data.mug_id
    mug_no = callback_data.mug_no
    offset = callback_data.current_offset
    mug: Optional[MugEntry]
    conn = await db.get_connection()
    mug = await get_mug_by_id(conn, query.message.chat.id, mug_id)
    if mug is None:
        await query.answer("Не удалось найти вашу кружку")
        return
    lst_used_at = (
        "<i>(никогда)</i>" if mug.taker_telegram is None else format_mug_used_at(mug)
    )
    msg_prefix = f"❯❯❯ №{mug_no} <b>{escapeHTML(mug.name)}</b>\n\nПоследнее использование: {lst_used_at}"
    if act == MugActionTy.VIEW:
        await query.message.edit_text(
            msg_prefix + "\nВыберете действие:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✍️ Переименовать",
                            callback_data=MugActionsQuery(
                                action_ty=MugActionTy.RENAME,
                                mug_id=mug_id,
                                mug_no=mug_no,
                                current_offset=offset,
                            ).pack(),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="❌ Удалить",
                            callback_data=MugActionsQuery(
                                action_ty=MugActionTy.ASK_DELETE,
                                mug_id=mug_id,
                                mug_no=mug_no,
                                current_offset=offset,
                            ).pack(),
                        ),
                        InlineKeyboardButton(
                            text="❮❮ Назад",
                            callback_data=MugNextPageQuery(offset=offset).pack(),
                        ),
                    ],
                ]
            ),
        )
    elif act == MugActionTy.RENAME:

        async def callback(mug_name: str, msg: Message):
            global diag
            mug_name = normalize_mug_name(mug_name)
            if mug_name is None:
                await msg.reply(
                    "❗️ Название кружки должно состоять из русских или английский букв, цифр и некоторых знаков. Попробуйте ещё раз:"
                )
                diag.set(msg.chat.id, DialogueTy.MugRename, callback)
                return
            conn = await db.get_connection()
            await conn.execute(
                "update mugs set name = ? where id = ?", [mug_name, mug_id]
            )
            await db.commit_changes()
            await conn.close()
            await msg.reply("✅ Имя кружки обновлено")

        await query.message.edit_text(
            msg_prefix + "\nВведите новое название:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🚫 Отменить",
                            callback_data=CancelDialogueQuery().pack(),
                        )
                    ]
                ]
            ),
        )
        diag.set(query.message.chat.id, DialogueTy.MugRename, callback)
    elif act == MugActionTy.ASK_DELETE:
        cdata = MugActionsQuery(
            action_ty=MugActionTy.VIEW,
            mug_id=mug_id,
            mug_no=mug_no,
            current_offset=offset,
        ).pack()
        await query.message.edit_text(
            msg_prefix + "\n\n<b>⚠️ Вы действительно хотите удалить кружку?</b>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❮❮ Назад",
                            callback_data=cdata,
                        ),
                        InlineKeyboardButton(
                            text="❌ Удалить",
                            callback_data=MugActionsQuery(
                                action_ty=MugActionTy.CONFIRM_DELETE,
                                mug_id=mug_id,
                                mug_no=mug_no,
                                current_offset=offset,
                            ).pack(),
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="🚫 Нет, не надо",
                            callback_data=cdata,
                        )
                    ],
                ]
            ),
        )
    elif act == MugActionTy.CONFIRM_DELETE:
        await conn.execute("DELETE FROM mugs WHERE id = ?", [mug_id])
        await db.commit_changes()
        await query.message.edit_text(
            f"✅ Кружка №{mug_no} ({escapeHTML(mug.name)}) удалена"
        )
