# Local shortcuts. Details: deploy/LOCAL-TESTING.md
.PHONY: help up down reset smoke test verify verify-all docker-test

help:        ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'

up:          ## deploy the local stack (PostgreSQL + migrations + API on :8000)
	docker compose -f deploy/docker-compose.yml up -d --build

down:        ## stop the stack, keep data
	docker compose -f deploy/docker-compose.yml down

reset:       ## stop the stack and delete its data
	docker compose -f deploy/docker-compose.yml down -v

smoke:       ## run the smoke test against an already-running API
	./deploy/local-smoke-test.sh

test:        ## unit + API + contract tests (no Docker)
	cd services/scheduler-service && .venv/bin/pytest -p no:warnings

verify:      ## deploy, wait, smoke test + integrity check (stack keeps running)
	./deploy/local-deploy-and-test.sh

verify-all:  ## fresh deploy, every test suite, then tear down (CI-like)
	./deploy/local-deploy-and-test.sh --fresh --suite all --down

docker-test: ## run every test suite inside Docker (no local Python needed), then clean up
	./deploy/docker-test.sh
