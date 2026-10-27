"""Обработка POST /api/reviews без привязки к HTTP-серверу."""

import json
import uuid

from app.llm import LLMClient


def _error_response(status: int, code: str, request_id: str) -> tuple[int, dict]:
    return status, {"error": {"code": code}, "request_id": request_id}


def handle_review(body: bytes, llm: LLMClient, *, deadline_s: float = 10.0) -> tuple[int, dict]:
    request_id = uuid.uuid4().hex
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _error_response(422, "invalid_request", request_id)

    if not isinstance(payload, dict):
        return _error_response(422, "invalid_request", request_id)
    diff = payload.get("diff")
    if not isinstance(diff, str) or not diff:
        return _error_response(422, "invalid_request", request_id)
    if len(diff) > 20000:
        return _error_response(413, "diff_too_large", request_id)

    result = llm.review(diff)
    return 200, {**result, "request_id": request_id}
