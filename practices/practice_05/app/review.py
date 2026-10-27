"""Обработка POST /api/reviews без привязки к HTTP-серверу."""

import json
import logging
import queue
import threading
import time
import uuid

from app.llm import LLMClient


def _error_response(status: int, code: str, request_id: str) -> tuple[int, dict]:
    return status, {"error": {"code": code}, "request_id": request_id}


def handle_review(body: bytes, llm: LLMClient, *, deadline_s: float = 10.0) -> tuple[int, dict]:
    started = time.monotonic()
    request_id = uuid.uuid4().hex

    def finish(response):
        status, payload = response
        logging.getLogger("reviews").info(
            "request_id=%s duration_ms=%d status=%d", request_id,
            int((time.monotonic() - started) * 1000), status)
        return status, payload

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return finish(_error_response(422, "invalid_request", request_id))

    if not isinstance(payload, dict):
        return finish(_error_response(422, "invalid_request", request_id))
    diff = payload.get("diff")
    if not isinstance(diff, str) or not diff:
        return finish(_error_response(422, "invalid_request", request_id))
    if len(diff) > 20000:
        return finish(_error_response(413, "diff_too_large", request_id))

    outcomes = queue.Queue(maxsize=1)

    def review():
        try:
            result = llm.review(diff)
        except Exception:
            outcomes.put((False, time.monotonic(), None))
        else:
            outcomes.put((True, time.monotonic(), result))

    deadline = time.monotonic() + deadline_s
    threading.Thread(target=review, daemon=True).start()
    try:
        succeeded, completed, result = outcomes.get(timeout=max(0.0, deadline - time.monotonic()))
    except queue.Empty:
        return finish(_error_response(504, "llm_timeout", request_id))
    if completed > deadline:
        return finish(_error_response(504, "llm_timeout", request_id))
    if not succeeded:
        return finish(_error_response(502, "llm_failed", request_id))
    return finish((200, {**result, "request_id": request_id}))
