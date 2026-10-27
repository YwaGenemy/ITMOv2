PY := .venv/bin/python

.PHONY: setup check test run mcp-demo

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q pytest mcp

check:
	sh scripts/check.sh

test: check

run:
	$(PY) -m app.server 8000

mcp-demo:
	$(PY) scripts/mcp_demo.py
