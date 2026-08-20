# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Every target runs through Docker Compose. If a target needs a host-level tool
# other than Docker, that is a bug in this file, not a prerequisite.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

COMPOSE := docker compose
RUN     := $(COMPOSE) run --rm app

.PHONY: help up down build migrate revision downgrade shell psql logs ps test test-integration lint licenses clean nuke

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.env:
	@cp .env.example .env
	@echo ""
	@echo "  Created .env from .env.example."
	@echo ""
	@echo "  Fill in these two before continuing — neither has a usable default:"
	@echo "    EMEYE_POSTGRES_PASSWORD   any non-empty string"
	@echo "    EMEYE_USER_AGENT          must carry a real contact address"
	@echo ""
	@echo "  Then re-run 'make up'."
	@echo ""
	@exit 1

up: .env ## Start postgres and the app container
	$(COMPOSE) up -d --build
	@echo "up. next: make migrate"

down: ## Stop containers, keep data
	$(COMPOSE) down

build: .env ## Rebuild the image
	$(COMPOSE) build

migrate: .env ## Apply migrations (alembic upgrade head)
	$(RUN) alembic upgrade head

revision: .env ## Autogenerate a migration: make revision m="add bronze tables"
	@test -n "$(m)" || (echo "usage: make revision m=\"message\"" && exit 1)
	$(RUN) alembic revision --autogenerate -m "$(m)"

downgrade: .env ## Roll back one migration
	$(RUN) alembic downgrade -1

shell: .env ## Bash shell in the app container
	$(COMPOSE) exec app bash

psql: .env ## psql shell on the warehouse
	$(COMPOSE) exec postgres psql -U $${EMEYE_POSTGRES_USER:-emeye} -d $${EMEYE_POSTGRES_DB:-emeye}

logs: ## Follow container logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

licenses: .env ## Check dependency license compatibility
	$(RUN) python scripts/check_licenses.py

# -- Wired in plan 01-03. Failing loudly is deliberate: a no-op 'make test'
# -- that exits 0 is the most dangerous target a Makefile can contain.
test: ## Run unit tests (implemented in plan 01-03)
	@echo "not wired yet — plan 01-03 owns the test harness" >&2
	@exit 2

test-integration: ## Run integration tests (implemented in plan 01-03)
	@echo "not wired yet — plan 01-03 owns the test harness" >&2
	@exit 2

lint: ## Run ruff and mypy (implemented in plan 01-03)
	@echo "not wired yet — plan 01-03 owns the lint config" >&2
	@exit 2

clean: ## Remove containers and the app image, keep the database volume
	$(COMPOSE) down --rmi local

nuke: ## Remove containers AND all data volumes. Destroys the warehouse.
	@echo "This deletes the warehouse volume permanently."
	@read -p "Type 'nuke' to confirm: " ans && [ "$$ans" = "nuke" ] || (echo "aborted" && exit 1)
	$(COMPOSE) down -v --rmi local
