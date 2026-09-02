PYTHON ?= python3
# Pre-commit hooks (mypy, pylint) usam `language: system`; alinhar ao .venv do projeto (requires-python 3.12).
PC_PYTHON ?= $(CURDIR)/.venv/bin/python

# migrate / seed-demo usam uv run para usar o Alembic e deps do projeto (ver README §4.1–4.2).
# Postgres do compose usa bind mount em ./docker-volumes/postgres; docker compose down -v não apaga esse diretório.

.PHONY: validate-setup pc-config pc-after-commit pc-run-all pc-run gen-token run-seed seed-demo seed-demo-python seed-demo-export ci ci-mypy migrate temporal-up temporal-down temporal-ui worker test-temporal docs-up docs-down

# Mirror GitHub Actions CI (see .github/workflows/ci.yml).
check-links:
	@uv run python resources/scripts/check_markdown_links.py

ci:
	@TRACING_ENABLED=false uv sync --all-extras --all-groups
	@TRACING_ENABLED=false uv run ruff check src
	@TRACING_ENABLED=false uv run python resources/scripts/check_markdown_links.py
	@TRACING_ENABLED=false uv run python -m pytest tests/unit tests/integration -m "not validation_integration"

# Optional: mypy is informational in CI (continue-on-error) but useful locally.
ci-mypy:
	@TRACING_ENABLED=false uv run mypy src

validate-setup:
	resources/scripts/validation_setup.sh

pc-config:
	@PYTHONPATH=src $(PC_PYTHON) -m pre_commit install --install-hooks

pc-after-commit:
	@PYTHONPATH=src $(PC_PYTHON) -m pre_commit run --from-ref origin/main --to-ref HEAD

pc-run-all:
	@PYTHONPATH=src $(PC_PYTHON) -m pre_commit run --all-files

pc-run:
	@PYTHONPATH=src $(PC_PYTHON) -m pre_commit run

gen-token:
	@PYTHONPATH=src uv run python resources/generate_jwt_token.py

run-seed:
	@PYTHONPATH=src python3 resources/scripts/seeds/seed_main.py

seed-demo:
	@PYTHONPATH=src uv run python resources/scripts/seeds/demo/apply_sql.py

seed-demo-python:
	@PYTHONPATH=src uv run python resources/scripts/seeds/demo/run.py

seed-demo-export:
	@PYTHONPATH=src uv run python resources/scripts/seeds/demo/export_sql.py

migrate:
	@PYTHONPATH=src uv run python -m alembic upgrade head

temporal-up:
	@docker compose up -d temporal

temporal-down:
	@docker compose stop temporal

temporal-ui:
	@echo "Temporal Web UI: http://localhost:8233"

worker:
	@PYTHONPATH=src TEMPORAL_ENABLED=true uv run python -m adapters.temporal.worker

test-temporal:
	@TRACING_ENABLED=false uv run python -m pytest tests/unit/temporal --cov-fail-under=0

docs-up:
	@docker compose --profile docs up -d docs
	@echo "Docs: http://localhost:8001"

docs-down:
	@docker compose --profile docs stop docs
