"""Execute the shipped JavaScript, not a Python copy of its rules."""

import subprocess
from pathlib import Path


def test_web_ui_behavior():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "--test", str(root / "tests/web_ui.test.cjs")],
        cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
