import asyncio
from fastapi import APIRouter, Depends

from pydantic import BaseModel
from enum import Enum
from typing import Optional

from database import commit_changes, get_connection
from telegram.commands import escapeHTML
from telegram.tgcore import BOT


from ..app import app
from .auth import authorization, AuthMethod
from .models import LockState, RFIDRead
from .apimodel import Error, LegacyException, Response
from models.activation import CURRENT_ACTIVATOR, ActivationThing


router = APIRouter(
    prefix="/v0",
    tags=["v0"],
)

LAST_READ_RFID: Optional[RFIDRead] = None
LOCK_STATE: LockState = LockState()


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
        SELECT null as id, id as owner_id, rfid_tag, '(user)' as name, 'user' AS ty
        FROM users
        WHERE users.rfid_tag = ?1
        UNION
        SELECT id, owner_id, rfid_tag, name, 'mug' AS ty
        FROM mugs
        WHERE mugs.rfid_tag = ?1
        """,
        [rfid_tag],
    )
    row = await cur.fetchone()
    if not row:
        LAST_READ_RFID = RFIDRead(serial=rfid_tag).created()
        raise LegacyException(Error.NOT_FOUND, "RFID tag does not exists")

    res = dict(zip([col[0] for col in cur.description], row))

    # TODO: checks
    LOCK_STATE.open()

    # TODO: move notifications to .telegram module
    if res["ty"] == "mug" and LAST_READ_RFID is not None and LAST_READ_RFID.is_user():
        # TODO: make less sql requests
        await cur.execute(
            "select telegram_id from users where id = ?", [res["owner_id"]]
        )
        tgid = (await cur.fetchone())[0]
        await BOT.send_message(
            tgid,
            ("⭐️" if res["owner_id"] == LAST_READ_RFID.user_id else "❗️")
            + f" Ваша кружка <b>«{res['name']}»</b> была взята из шкафа",
        )

    LAST_READ_RFID = RFIDRead(
        serial=rfid_tag, mug_id=res["id"], user_id=res["owner_id"]
    ).created()

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


@router.post("/activate")
async def activate_tag(
    method: AuthMethod = Depends(authorization),
) -> Response[ActivationResult]:
    global LAST_READ_RFID, CURRENT_ACTIVATOR, BOT
    if method != AuthMethod.BOX:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")
    if not LAST_READ_RFID or LAST_READ_RFID.is_outdated():
        raise LegacyException(Error.NOT_FOUND, "No actual cards scanned")
    if LAST_READ_RFID.known():
        if LAST_READ_RFID.is_mug():
            conn = await get_connection()
            await conn.execute(
                "select users.id as id, users.telegram_id as telegram_id, mugs.name as name from mugs inner join users on users.id = mugs.owner_id where users.id = ?",
                [LAST_READ_RFID.user_id],
            )
            res = await conn.fetchone()
            chat_id = res[1]
            name = res[2]
            LAST_READ_RFID = None
            await BOT.send_message(
                chat_id,
                f"❗️ Ваша кружка «<b>{escapeHTML(name)}</b>» найдена грязной и была отправлена на парковку",
            )
            # TODO: move sending messages to .telegram module
            return Response(response=ActivationResult.DIRTY)
        else:
            raise LegacyException(
                Error.NOTHING_TO_DO, "Cannot activate thing that not mug"
            )
    serial = LAST_READ_RFID.serial
    LAST_READ_RFID = None
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


@router.post("/invite")
async def invite(method: AuthMethod = Depends(authorization)) -> Response[None]:
    if method != AuthMethod.BOX:
        raise LegacyException(Error.INVALID_TOKEN, "No access for this auth method")
    return Response(response=None)


app.include_router(router)
