import pytest

from mcp_server.diffscan import MAX_CHARS, DiffError, inspect

TOKEN = "ghp_" + "a1B2" * 9
DIFF = f"""--- a/app/config.py
+++ b/app/config.py
@@ -1,3 +1,4 @@
 import os
-DEBUG = True
+DEBUG = False
+GITHUB_TOKEN = "{TOKEN}"
 db_password = "hunter22"
"""


def test_reports_files_and_secret_locations_without_values():
    result = inspect(DIFF)

    assert result["files"] == [{"path": "app/config.py", "added": 2, "removed": 1}]
    assert {(s["kind"], s["line"], s["side"]) for s in result["secrets"]} == {
        ("github_token", 3, "new"), ("password_or_key", 4, "new")}
    assert TOKEN not in str(result) and "hunter22" not in str(result)


def test_redaction_keeps_line_count():
    redacted = inspect(DIFF)["redacted_diff"]

    assert redacted.count("\n") == DIFF.count("\n")
    assert 'db_password = "[REDACTED]"' in redacted


def test_private_key_block_is_fully_redacted():
    diff = ("+++ b/key.pem\n@@ -0,0 +1,3 @@\n+-----BEGIN RSA PRIVATE KEY-----\n"
            "+MIIEsecretbody\n+-----END RSA PRIVATE KEY-----\n")
    result = inspect(diff)

    assert [s["kind"] for s in result["secrets"]] == ["private_key"]
    assert "MIIE" not in result["redacted_diff"]


@pytest.mark.parametrize("bad, code", [
    ("", "invalid_request"),
    (None, "invalid_request"),
    ("просто текст", "not_a_diff"),
    ("+++ b/x\n@@ -1 +1 @@\n" + "+" * MAX_CHARS, "diff_too_large"),
])
def test_bad_input_is_rejected_with_code(bad, code):
    with pytest.raises(DiffError) as err:
        inspect(bad)
    assert err.value.code == code
