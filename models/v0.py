import asyncio
from time import time
from typing import Optional
from pydantic import BaseModel

class SharedBox[T]:
    value: Optional[T] = None

    def __init__(self, init: Optional[T] = None):
        self.value = init
    def set(self, value: T):
        self.value = value
    def unset(self):
        self.value = None

    def is_none(self) -> bool:
        return self.value is None

class RFIDRead(BaseModel):
    serial: Optional[str]
    mug_id: Optional[int] = None
    user_id: Optional[int] = None
    telegram_id: Optional[int] = None
    telegram_name: Optional[str] = None
    created_at: float = 0.0

    def created(self) -> "RFIDRead":
        self.created_at = time()
        return self

    def is_outdated(self, timeout: float = 45.0) -> bool:
        return self.created_at + timeout < time()

    def known(self):
        return self.user_id is not None

    def is_user(self):
        return self.known() and self.mug_id is None

    def is_mug(self):
        return self.known() and self.mug_id is not None


class LockState:
    ev: asyncio.Event
    val: bool

    def __init__(self):
        self.val = False
        self.ev = asyncio.Event()

    def open(self):
        self.val = True
        self.ev.set()

    async def is_open(self) -> bool:
        if not self.val:
            await self.ev.wait()
        self.ev.clear()
        self.val = False
        return True

LOCK_STATE: LockState = LockState()
LAST_READ_RFID: SharedBox[RFIDRead] = SharedBox()


