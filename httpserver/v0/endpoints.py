import asyncio
from time import time
from fastapi import APIRouter, Depends

from pydantic import BaseModel
from enum import Enum
from typing import Optional

from database import commit_changes, get_connection
from telegram.commands import escapeHTML
from telegram.tgcore import BOT


from ..app import app
from .auth import authorization, AuthMethod
from .apimodel import Error, LegacyException, Response
from models.activation import CURRENT_ACTIVATOR, ActivationThing
from models.v0 import LockState, RFIDRead, LOCK_STATE, LAST_READ_RFID


router = APIRouter(
    prefix="/v0",
    tags=["v0"],
)

class RFIDMug(BaseModel):
    ok: bool = True
    ty: str
    name: str


@router.post("/rfid")
async def read_rfid(
    rfid_tag: str, method: AuthMethod = Depends(authorization)
) -> RFIDMug:
    global LAST_READ_RFID, LOCK_STATE, BOT
    if method != AuthMethod.BOX:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")

    cur = await get_connection()
    await cur.execute(
        """
        SELECT
            null as id,
            users.id as owner_id,
            users.rfid_tag,
            '(user)' as name,
            'user' AS ty,
            telegram_id,
            telegram_name,
            0 as delta,
            (mugs.id is not null) as is_mug
        FROM users
            LEFT JOIN mugs ON mugs.owner_id = users.id
        WHERE users.rfid_tag = ?1
        UNION
        SELECT
            mugs.id as id,
            mugs.owner_id as owner_id,
            mugs.rfid_tag as rfid_tag,
            mugs.name as name,
            'mug' AS ty,
            users.telegram_id as telegram_id,
            users.telegram_name as telegram_name,
            (mugs.last_taken_at - mugs.last_returned_at) as delta,
            false as is_mug
        FROM mugs INNER JOIN users ON mugs.owner_id = users.id
        WHERE mugs.rfid_tag = ?1
        """,
        [rfid_tag],
    )
    row = await cur.fetchone()
    if not row:
        LAST_READ_RFID.set(RFIDRead(serial=rfid_tag).created())
        raise LegacyException(Error.NOT_FOUND, "RFID tag does not exists")

    res = dict(zip([col[0] for col in cur.description], row))

    # Check if last LAST_READ_RFID actual
    if not LAST_READ_RFID.is_none() and LAST_READ_RFID.value.is_outdated():
        LAST_READ_RFID.unset()

    # TODO: checks
    if res["ty"] == "user" and res["is_mug"] == 1:
        # Do not open door if user doesn't have any mugs
        LOCK_STATE.open()
    # TODO: move notifications to .telegram module
    elif res["ty"] == "mug":
        if not LAST_READ_RFID.is_none() and LAST_READ_RFID.value.is_user() and res["delta"] < 0:
            tgid = res["telegram_id"]
            await cur.execute(
                "UPDATE mugs SET last_taken_at = ?, last_taken_by = ? WHERE id = ?",
                [int(time()), LAST_READ_RFID.value.user_id, res["id"]],
            )
            await commit_changes()
            taker_name = (
                escapeHTML(LAST_READ_RFID.value.telegram_name)
                if LAST_READ_RFID.value.telegram_name is not None
                else "другим пользователем"
            )
            await BOT.send_message(
                tgid,
                ("⭐️" if res["owner_id"] == LAST_READ_RFID.value.user_id else "❗️")
                + f" Ваша кружка <b>«{res['name']}»</b> была взята из шкафа"
                + (
                    ". Пожалуйста, при возвращении <b>прикладывайте кружку</b>, а не карту."
                    if res["owner_id"] == LAST_READ_RFID.value.user_id
                    else f' <a href="tg://user?id={LAST_READ_RFID.value.telegram_id}">{taker_name}</a>.'
                ),
            )
            if res["owner_id"] != LAST_READ_RFID.value.user_id:
                await BOT.send_message(
                    LAST_READ_RFID.value.telegram_id,
                    f"😡 Вы взяли чужую кружку «<b>{escapeHTML(res['name'])}</b>». Пожалуйста, верните её в шкаф",
                )
        else:  # mug returned
            LOCK_STATE.open()
            await cur.execute(
                "UPDATE mugs SET last_returned_at = ? WHERE id = ?",
                [int(time()), res["id"]],
            )
            await commit_changes()

    LAST_READ_RFID.set(RFIDRead(
        serial=rfid_tag,
        mug_id=res["id"],
        user_id=res["owner_id"],
        telegram_id=res["telegram_id"],
        telegram_name=res["telegram_name"],
    ).created())

    return RFIDMug(ty=res["ty"], name=res["name"])


class LockState(BaseModel):
    is_lock_open: bool
    is_mug_waiting: bool = False


@router.get("/state")
async def get_state(
    lp: int = 25, method: AuthMethod = Depends(authorization)
) -> Response[LockState]:
    global LOCK_STATE
    if method != AuthMethod.LOCK:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")

    if not (0 <= lp <= 60):
        raise LegacyException(Error.INVALID_INPUT, "`lp` should be in 0..=60 seconds")

    try:
        async with asyncio.timeout(lp):
            await LOCK_STATE.is_open()
        return Response(response=LockState(is_lock_open=True))
    except TimeoutError:
        return Response(response=LockState(is_lock_open=False))


class ActivationResult(Enum):
    USER = "user"
    MUG = "mug"
    DIRTY = "dirty"


@router.post("/rfid/register")
async def register_tag(
    method: AuthMethod = Depends(authorization),
) -> Response[ActivationResult]:
    global LAST_READ_RFID, CURRENT_ACTIVATOR, BOT
    if method != AuthMethod.BOX:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")
    if LAST_READ_RFID.is_none() or LAST_READ_RFID.value.is_outdated() or LAST_READ_RFID.value.serial is None:
        raise LegacyException(Error.NOT_FOUND, "No actual cards scanned")
    if LAST_READ_RFID.value.known():
        raise LegacyException(Error.NOTHING_TO_DO, "Cannot activate known rfid tag")
    serial = LAST_READ_RFID.value.serial
    LAST_READ_RFID.unset()
    if CURRENT_ACTIVATOR.ty == ActivationThing.UpdateCard:
        conn = await get_connection()
        await conn.execute(
            "insert into users(telegram_id, rfid_tag) values (?1, ?2) on conflict(telegram_id) do update set rfid_tag=?2",
            [CURRENT_ACTIVATOR.user_id, serial],
        )
        await commit_changes()
        await CURRENT_ACTIVATOR.activate()
        return Response(response=ActivationResult.USER)
    elif CURRENT_ACTIVATOR.ty == ActivationThing.CreateMug:
        conn = await get_connection()
        await conn.execute(
            "insert into mugs(name, owner_id, rfid_tag) select ?, id, ? from users where users.telegram_id = ?",
            [CURRENT_ACTIVATOR.name, serial, CURRENT_ACTIVATOR.user_id],
        )
        await commit_changes()
        await CURRENT_ACTIVATOR.activate()
        return Response(response=ActivationResult.MUG)
    else:
        raise LegacyException(Error.NOT_FOUND, "Nothing to activate")


@router.post("/rfid/dirty")
async def report_dirty_mug(
    method: AuthMethod = Depends(authorization),
) -> Response[str]:
    global LAST_READ_RFID, BOT
    if method != AuthMethod.BOX:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")
    if LAST_READ_RFID.value.is_mug():
        conn = await get_connection()
        await conn.execute(
            "select users.id as id, users.telegram_id as telegram_id, mugs.name as name from mugs inner join users on users.id = mugs.owner_id where users.id = ?",
            [LAST_READ_RFID.value.user_id],
        )
        res = await conn.fetchone()
        chat_id = res[1]
        name = res[2]
        LAST_READ_RFID.unset()
        await BOT.send_message(
            chat_id,
            f"❗️ Ваша кружка «<b>{escapeHTML(name)}</b>» найдена грязной и была отправлена на парковку",
        )
        # TODO: move sending messages to .telegram module
        return Response(response=name)
    else:
        raise LegacyException(Error.NOTHING_TO_DO, "Cannot activate thing that not mug")


app.include_router(router)
