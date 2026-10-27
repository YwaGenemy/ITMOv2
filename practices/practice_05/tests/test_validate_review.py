import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".opencode/skills/diff-review/scripts/validate_review.py"
spec = importlib.util.spec_from_file_location("validate_review", SCRIPT)
validate_review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate_review)
validate = validate_review.validate

DIFF = "--- a/app/a.py\n+++ b/app/a.py\n@@ -10,2 +10,3 @@\n x = 1\n+y = json.loads(body)\n z = 3\n"


def risk(**over):
    return {"file": "app/a.py", "line": 11, "evidence": "json.loads(body)",
            "risk": "нет обработки невалидного JSON", **over}


def review(*risks):
    return {"summary": "s", "risks": list(risks), "checks": ["pytest"]}


def test_evidence_on_added_line_is_accepted():
    assert validate(DIFF, review(risk())) == []


def test_wrong_line_or_evidence_is_rejected():
    assert "нет в новой версии" in validate(DIFF, review(risk(line=99)))[0]
    assert "evidence" in validate(DIFF, review(risk(evidence="eval(")))[0]


def test_more_than_three_risks_is_rejected():
    assert any("> 3" in e for e in validate(DIFF, review(*[risk()] * 4)))
