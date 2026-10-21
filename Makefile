.PHONY: verify
verify:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest
