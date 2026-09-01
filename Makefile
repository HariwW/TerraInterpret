.PHONY: setup dev test lint

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

dev:
	.venv/bin/i2rsi --reload

test:
	.venv/bin/pytest --cov=i2rsi --cov-report=term-missing

lint:
	.venv/bin/ruff check i2rsi tests
