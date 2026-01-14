PYTHON ?= python3

.PHONY: validate-setup validate-seed validate-down validate-logs validate-test

validate-setup:
	resources/scripts/validation_setup.sh

validate-seed:
	docker compose run --rm --entrypoint "" app bash -c "python resources/scripts/wait_for_db.py && python resources/scripts/validation_seed.py"

validate-down:
	docker compose down

validate-logs:
	docker compose logs --tail=50 app

validate-test:
	resources/scripts/validation_setup.sh
	make validate-seed
	DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/agent_router PYTEST_ADDOPTS="--no-cov --cov-fail-under=0" bash -c "source .venv/bin/activate && PYTHONPATH=src pytest src/tests/validation_integration -m validation_integration"
