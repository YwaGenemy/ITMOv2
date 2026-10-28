"""Проверка diff перед передачей модели: размер (API-1) и секреты (SEC-1)."""

import re

MAX_CHARS = 20_000
REDACTED = "[REDACTED]"

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
KEY_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
KEY_END = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")
# (вид секрета, шаблон, номер группы со значением; 0 — заменить всё совпадение)
PATTERNS = [
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), 0),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/-]{16,}=*)"), 1),
    ("password_or_key", re.compile(
        r"(?i)\w*(?:password|passwd|pwd|secret|api_?key|token)\w*\s*[:=]\s*[\"']"
        r"(?!\[REDACTED\])([^\"']{4,})[\"']"), 1),
]


class DiffError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def inspect(diff: object) -> dict:
    if not isinstance(diff, str) or not diff.strip():
        raise DiffError("invalid_request", "diff должен быть непустой строкой")
    if len(diff) > MAX_CHARS:
        raise DiffError("diff_too_large",
                        f"{len(diff)} символов > {MAX_CHARS}; вход не обрезается")
    lines = diff.split("\n")
    if not any(l.startswith("+++ ") for l in lines) or not any(HUNK.match(l) for l in lines):
        raise DiffError("not_a_diff", "нет заголовков '+++' и '@@': это не unified diff")

    files: list[dict] = []
    secrets: list[dict] = []
    out: list[str] = []
    old_no = new_no = 0
    in_key = False
    for raw in lines:
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            files.append({"path": path[2:] if path.startswith("b/") else path,
                          "added": 0, "removed": 0})
            out.append(raw)
            continue
        if raw.startswith("--- ") or not files:
            out.append(raw)
            continue
        if m := HUNK.match(raw):
            old_no, new_no = int(m[1]), int(m[2])
            out.append(raw)
            continue
        prefix, text = raw[:1], raw[1:]
        if prefix not in "+- " or raw == "":
            out.append(raw)
            continue
        side, line_no = ("old", old_no) if prefix == "-" else ("new", new_no)
        where = {"file": files[-1]["path"], "line": line_no, "side": side}

        if in_key or KEY_BEGIN.search(text):
            if not in_key:
                secrets.append({"kind": "private_key", **where})
            in_key = not KEY_END.search(text)
            text = REDACTED
        else:
            for kind, pattern, group in PATTERNS:
                if pattern.search(text):
                    secrets.append({"kind": kind, **where})
                    text = pattern.sub(lambda m: _redact(m, group), text)
        out.append(prefix + text)

        if prefix == "+":
            files[-1]["added"] += 1
        elif prefix == "-":
            files[-1]["removed"] += 1
        if prefix != "+":
            old_no += 1
        if prefix != "-":
            new_no += 1

    return {
        "chars": len(diff),
        "limit": MAX_CHARS,
        "files": files,
        "secrets": secrets,
        "redacted_diff": "\n".join(out),
    }


def _redact(match: re.Match, group: int) -> str:
    if group == 0:
        return REDACTED
    start, end = match.span(group)
    base = match.start()
    whole = match.group(0)
    return whole[:start - base] + REDACTED + whole[end - base:]
