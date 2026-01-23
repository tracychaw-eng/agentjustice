# Makefile for Docker-based evaluation runs
# Usage: make docker-<target>

.PHONY: docker-build docker-preflight docker-smoke docker-canonical docker-adversarial docker-all docker-clean

# Build the Docker image
docker-build:
	docker compose build

# Run preflight check (validates MCP connectivity)
docker-preflight:
	docker compose run --rm evaluator python scripts/run_evaluation.py --preflight

# Run smoke test (3 tasks, quick validation)
docker-smoke:
	docker compose run --rm evaluator python scripts/run_evaluation.py --smoke-test

# Run canonical track only (50 tasks)
docker-canonical:
	docker compose run --rm evaluator python scripts/run_evaluation.py --track canonical

# Run adversarial track only
docker-adversarial:
	docker compose run --rm evaluator python scripts/run_evaluation.py --track adversarial

# Run full evaluation (both tracks) - default
docker-all:
	docker compose run --rm evaluator python scripts/run_evaluation.py

# Clean up Docker resources
docker-clean:
	docker compose down --rmi local --volumes --remove-orphans
