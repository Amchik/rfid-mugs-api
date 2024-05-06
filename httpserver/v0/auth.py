from enum import Enum
from fastapi import Header
from .apimodel import LegacyException, Error

from models.config import get_config


class AuthMethod(Enum):
    BOX = "box"
    LOCK = "lock"


def authorization(authorization: str = Header(...)) -> AuthMethod:
    if authorization is None:
        raise LegacyException(Error.UNAUTHORIZED, "No header present")
    cfg = get_config()
    spl = authorization.split(" ", 1)
    if len(spl) != 2:
        raise LegacyException(Error.UNAUTHORIZED, "Invalid header format")
    [method, token] = spl

    if method == "box" and cfg.box_token() == token:
        return AuthMethod.BOX
    elif method == "lock" and cfg.lock_token() == token:
        return AuthMethod.LOCK
    else:
        raise LegacyException(Error.INVALID_TOKEN, "Invalid token or method")
