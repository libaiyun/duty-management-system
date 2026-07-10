.PHONY: check lint format type-check test

check:
	@bash check.sh

lint:
	ruff check backend/app

format:
	ruff format backend/app backend/tests

type-check:
	mypy

test:
	pytest
