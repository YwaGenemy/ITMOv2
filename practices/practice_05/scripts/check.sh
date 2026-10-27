#!/bin/sh
# Единственная проверка проекта: синтаксис + тесты. Её же запускает hook после правок.
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python
"$PY" -m compileall -q app mcp_server .opencode/skills/diff-review/scripts
"$PY" -m pytest -q -p no:cacheprovider
