"""Проверка ревью по OUT-1/QA-1: схема, не больше трёх рисков, evidence есть в строке diff.

Использование: validate_review.py <diff-файл> <review.json>. Код выхода 0 — OK.
"""

import json
import re
import sys

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def new_side_lines(diff: str) -> dict[tuple[str, int], str]:
    """(файл, номер строки новой версии) -> текст строки, для '+' и контекстных строк."""
    lines: dict[tuple[str, int], str] = {}
    path, no = None, 0
    for raw in diff.split("\n"):
        if raw.startswith("+++ "):
            path = raw[4:].strip().removeprefix("b/")
        elif raw.startswith("--- "):
            continue
        elif m := HUNK.match(raw):
            no = int(m[1])
        elif path and raw[:1] in ("+", " "):
            lines[(path, no)] = raw[1:]
            no += 1
    return lines


def validate(diff: str, review: object) -> list[str]:
    if not isinstance(review, dict):
        return ["ревью должно быть JSON-объектом"]
    errors = []
    if not isinstance(review.get("summary"), str) or not review["summary"].strip():
        errors.append("summary: нужна непустая строка")
    checks = review.get("checks")
    if not isinstance(checks, list) or not all(isinstance(c, str) for c in checks):
        errors.append("checks: нужен список строк")
    risks = review.get("risks")
    if not isinstance(risks, list):
        return errors + ["risks: нужен список"]
    if len(risks) > 3:
        errors.append(f"risks: {len(risks)} > 3")

    lines = new_side_lines(diff)
    for i, risk in enumerate(risks, 1):
        where = f"risks[{i}]"
        if not isinstance(risk, dict):
            errors.append(f"{where}: нужен объект")
            continue
        for field in ("file", "evidence", "risk"):
            if not isinstance(risk.get(field), str) or not risk[field].strip():
                errors.append(f"{where}.{field}: нужна непустая строка")
        line = risk.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or line < 1:
            errors.append(f"{where}.line: нужно целое >= 1")
            continue
        text = lines.get((risk.get("file"), line))
        if text is None:
            errors.append(f"{where}: строки {risk.get('file')}:{line} нет в новой версии diff")
        elif isinstance(risk.get("evidence"), str) and risk["evidence"].strip() not in text:
            errors.append(f"{where}.evidence: не найдено в строке {line}: {text.strip()!r}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        diff = f.read()
    try:
        with open(argv[2], encoding="utf-8") as f:
            review = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAIL\n- невалидный JSON: {e}")
        return 1
    errors = validate(diff, review)
    if errors:
        print("FAIL\n" + "\n".join(f"- {e}" for e in errors))
        return 1
    print(f"OK: {len(review['risks'])} risk(s), evidence совпадает со строками diff")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
