from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel
from time import time


class ActivationThing(Enum):
    Nothing = "not"
    CreateMug = "mug"
    UpdateCard = "user"


class RFIDActivation(BaseModel):
    created_at: float = 0.0
    ty: ActivationThing
    user_id: int
    msg_id: int
    name: Optional[str] = None
    callback: Any = None

    def set(
        self,
        ty: ActivationThing,
        user_id: int,
        msg_id: int,
        name: Optional[str] = None,
        callback: Any = None,
    ):
        self.ty = ty
        self.user_id = user_id
        self.msg_id = msg_id
        self.name = name
        self.callback = callback
        self.created_at = time()

    def created(self) -> "RFIDActivation":
        self.created_at = time()
        return self

    def is_outdated(self, outdated_in: float = 45):
        return time() > self.created_at + outdated_in

    def outdate(self):
        self.created_at = 0.0

    async def activate(self):
        self.outdate()
        try:
            await self.callback(self)
        except Exception as err:
            print("Failed to call activation callback: ", err)


CURRENT_ACTIVATOR: RFIDActivation = RFIDActivation(
    ty=ActivationThing.Nothing, user_id=0, msg_id=0
)
