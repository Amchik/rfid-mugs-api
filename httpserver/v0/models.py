import asyncio
from time import time
from typing import Optional
from pydantic import BaseModel


class RFIDRead(BaseModel):
    serial: str
    mug_id: Optional[int] = None
    user_id: Optional[int] = None
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
