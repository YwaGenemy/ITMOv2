import json
import uuid

import pytest

from app.llm import FakeLLM
from app.review import handle_review


@pytest.mark.parametrize("body", [
    b"", b"not json", b'{"diff":', b'\xff',
    b"null", b"[]", b'"text"', b"42", b"true",
    b"{}", b'{"diff": null}', b'{"diff": 42}',
    b'{"diff": false}', b'{"diff": []}', b'{"diff": {}}',
    b'{"diff": ""}',
])
def test_invalid_request_is_rejected_without_llm_call(body):
    llm = FakeLLM()

    status, payload = handle_review(body, llm)

    assert status == 422
    request_id = payload["request_id"]
    assert payload == {"error": {"code": "invalid_request"}, "request_id": request_id}
    parsed_id = uuid.UUID(hex=request_id)
    assert parsed_id.version == 4
    assert parsed_id.hex == request_id
    assert llm.calls == []


@pytest.mark.parametrize("character", ["a", "😀"])
def test_20001_code_points_are_rejected_without_llm_call(character):
    llm = FakeLLM()
    body = json.dumps({"diff": character * 20001}).encode()

    status, payload = handle_review(body, llm)

    assert status == 413
    request_id = payload["request_id"]
    assert payload == {"error": {"code": "diff_too_large"}, "request_id": request_id}
    parsed_id = uuid.UUID(hex=request_id)
    assert parsed_id.version == 4
    assert parsed_id.hex == request_id
    assert llm.calls == []


@pytest.mark.parametrize("diff", ["a" * 20000, "😀" * 20000, " \n\t "])
@pytest.mark.parametrize("ensure_ascii", [True, False])
def test_valid_diff_is_passed_to_llm_once_without_changes(diff, ensure_ascii):
    llm = FakeLLM()
    body = json.dumps({"diff": diff}, ensure_ascii=ensure_ascii).encode()

    status, payload = handle_review(body, llm)

    assert status == 200
    assert {"summary", "risks", "checks", "request_id"} <= payload.keys()
    parsed_id = uuid.UUID(hex=payload["request_id"])
    assert parsed_id.version == 4
    assert parsed_id.hex == payload["request_id"]
    assert llm.calls == [diff]
