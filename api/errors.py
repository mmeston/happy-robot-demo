from typing import Any, Dict, Optional

from fastapi import HTTPException


def error_payload(
    error_code: str,
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": False,
        "error_code": error_code,
        "message": message,
    }

    if field:
        payload["field"] = field

    if details:
        payload["details"] = details

    return payload


def raise_tool_error(
    status_code: int,
    error_code: str,
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=error_payload(error_code, message, field, details),
    )
