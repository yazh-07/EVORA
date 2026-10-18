"""Shared request-validation mapping for draft 0.3.0 ApiError."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def invalid_request(
    _request: Request, _exception: RequestValidationError
) -> JSONResponse:
    # Validation errors can contain evidence, tokens, attacker-controlled field
    # names and non-JSON-serializable context. Do not echo or log them.
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_INPUT", "message": "Invalid request input."},
    )
