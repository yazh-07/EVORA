"""Shared request-validation mapping for draft 0.3.0 ApiError."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AccessError(Exception):
    """Safe, fixed access failures; never retain submitted credentials/IDs."""

    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


async def access_error(_request: Request, exception: AccessError) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if exception.status_code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=exception.status_code,
        content={"code": exception.code, "message": str(exception)},
        headers=headers,
    )


async def invalid_request(
    _request: Request, _exception: RequestValidationError
) -> JSONResponse:
    # Validation errors can contain evidence, tokens, attacker-controlled field
    # names and non-JSON-serializable context. Do not echo or log them.
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_INPUT", "message": "Invalid request input."},
    )
