from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

class CircleCueError(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

class NotFoundError(CircleCueError):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND, details=details)

class ValidationError(CircleCueError):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)

class UnauthorizedError(CircleCueError):
    def __init__(self, message: str = "Authentication required", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="UNAUTHORIZED", status_code=status.HTTP_401_UNAUTHORIZED, details=details)

class ForbiddenError(CircleCueError):
    def __init__(self, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN, details=details)

class StateConflictError(CircleCueError):
    def __init__(self, message: str = "State conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="STATE_CONFLICT", status_code=status.HTTP_409_CONFLICT, details=details)

class AIParseError(CircleCueError):
    def __init__(self, message: str = "AI failed to parse input", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="AI_PARSE_ERROR", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, details=details)

def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CircleCueError)
    async def circlecue_error_handler(request: Request, exc: CircleCueError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            }
        )
