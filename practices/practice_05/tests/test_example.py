import json

from app.llm import FakeLLM
from app.review import handle_review

DIFF = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n"


def test_valid_diff_returns_review_and_calls_llm_once():
    llm = FakeLLM()
    status, payload = handle_review(json.dumps({"diff": DIFF}).encode(), llm)

    assert status == 200
    assert {"summary", "risks", "checks", "request_id"} <= payload.keys()
    assert llm.calls == [DIFF]
