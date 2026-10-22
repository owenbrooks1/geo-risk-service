.PHONY: verify demo serve
verify:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest

# Generate seed data, assess every login, evaluate against truth, print the report.
demo:
	uv run --locked python -m geo_risk_service.service.run

# Serve the stored results on http://127.0.0.1:8000 (local only).
serve:
	uv run --locked uvicorn --factory geo_risk_service.service.api:default_app --host 127.0.0.1 --port 8000
