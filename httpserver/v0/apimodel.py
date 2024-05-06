from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from enum import Enum
from typing import Literal, Optional

from ..app import app


class Response[T](BaseModel):
    ok: Literal[True] = True
    response: T

    # def __init__(self, response: T, ok: bool = True):
    #     self.ok = ok
    #     self.response = response


class Error(Enum):
    UNAUTHORIZED = 1
    INVALID_TOKEN = 2
    INVALID_INPUT = 3
    INTERNAL = 4
    ENDPOINT_NOT_EXISTS = 5
    NOT_FOUND = 6
    CONFLICT = 7
    NOTHING_TO_DO = 8
    OUTDATED_API_VERSION = 9


class LegacyException(Exception):
    idx: int = -1
    why: str = ""

    def __init__(self, err: Error, why: Optional[str] = None):
        self.idx = err.value
        self.why = f"{err.name}" if why is None else f"{err.name}: {why}"


@app.exception_handler(LegacyException)
async def v0_exception_handler(request: Request, exc: LegacyException):
    return JSONResponse(
        status_code=400,
        content={"ok": False, "error": exc.idx, "why": exc.why},
    )


@app.exception_handler(RequestValidationError)
async def v0_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"ok": False, "error": Error.INVALID_INPUT.value, "why": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def v0_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": Error.ENDPOINT_NOT_EXISTS.value,
            "why": exc.detail,
        },
    )
