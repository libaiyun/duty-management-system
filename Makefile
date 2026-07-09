.PHONY: check lint format type-check test

check:
	@bash check.sh

lint:
	flake8 backend/app

format:
	black backend/app backend/tests

type-check:
	mypy

test:
	pytest
