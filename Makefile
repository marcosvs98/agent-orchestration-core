PYTHON ?= python3
# Pre-commit hooks (mypy, pylint) usam `language: system`; alinhar ao .venv do projeto (requires-python 3.12).
PC_PYTHON ?= $(CURDIR)/.venv/bin/python

# migrate / seed-demo usam uv run para usar o Alembic e deps do projeto (ver README §4.1–4.2).
# Postgres do compose usa bind mount em ./docker-volumes/postgres; docker compose down -v não apaga esse diretório.

.PHONY: validate-setup pc-config pc-after-commit pc-run-all pc-run gen-admin-token run-seed seed-demo seed-demo2 test-flow-demo test-trace-hierarchy serve-conversation-test

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
	@PYTHONPATH=src python3 resources/generate_jwt_token.py

run-seed:
	@PYTHONPATH=src python3 resources/scripts/seeds/seed_main.py

seed-demo:
	@PYTHONPATH=src uv run python resources/scripts/seeds/demo/run.py

seed-demo2:
	@PYTHONPATH=src uv run python resources/scripts/seeds/demo_2/run.py

test-flow-demo:
	@cd $(shell pwd) && PYTHONPATH=.:src:resources python3 resources/scripts/examples/execute_flow_demo.py

test-flow-demo-2:
	@cd $(shell pwd) && PYTHONPATH=.:src:resources python3 resources/scripts/examples/execute_flow_demo_direct.py

test-trace-hierarchy:
	@cd $(shell pwd) && PYTHONPATH=.:src:resources python3 resources/scripts/test_trace_hierarchy.py

migrate:
	@PYTHONPATH=src uv run python -m alembic upgrade head

serve-conversation-test:
	@echo "Serving conversation test frontend at http://localhost:9000"
	@echo "Ensure the API is running (e.g. uv run uvicorn src.app:create_app --factory --host 0.0.0.0 --port 8000)"
	@cd resources/conversation-test && python3 -m http.server 9000
