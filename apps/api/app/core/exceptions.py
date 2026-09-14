from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class PosterPilotError(Exception):
    def __init__(self, message: str, *, code: str = "application_error", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PosterPilotError)
    async def handle_posterpilot_error(
        _request: Request,
        error: PosterPilotError,
    ) -> JSONResponse:
        payload: dict[str, Any] = {
            "error": {
                "code": error.code,
                "message": error.message,
            }
        }
        return JSONResponse(status_code=error.status_code, content=payload)
