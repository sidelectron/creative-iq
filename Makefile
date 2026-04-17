# CreativeIQ — local tooling (use a venv: see README "Python environment")
.PHONY: up up-dev down migrate test lint buckets venv install-deps

PYTHON ?= python

# Prefer project .venv interpreter when it exists (works with Git Bash + cmd + Unix).
VENV_WIN := $(CURDIR)/.venv/Scripts/python.exe
VENV_POSIX := $(CURDIR)/.venv/bin/python
ifneq ($(wildcard $(VENV_WIN)),)
  PYRUN := "$(VENV_WIN)"
else ifneq ($(wildcard $(VENV_POSIX)),)
  PYRUN := "$(VENV_POSIX)"
else
  PYRUN := $(PYTHON)
endif

## Create .venv (does not activate your shell). Then run: make install-deps
venv:
	$(PYTHON) -m venv .venv
	@echo "Created .venv. Next:"
	@echo "  Windows (PowerShell): .\\.venv\\Scripts\\Activate.ps1"
	@echo "  Windows (cmd):        .venv\\Scripts\\activate.bat"
	@echo "  macOS/Linux:          source .venv/bin/activate"
	@echo "Then: make install-deps   (or: $(PYRUN) -m pip install -e \".[dev,google]\")"

## Install / upgrade deps into the active interpreter OR into .venv if present and not activated
install-deps:
	$(PYRUN) -m pip install --upgrade pip
	$(PYRUN) -m pip install -e ".[dev,google]"

up:
	docker compose up -d

## Docker with bind-mount + pip on boot + --reload (slower; use when editing Python live)
up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

down:
	docker compose down

migrate:
	$(PYRUN) -m alembic upgrade head

test:
	$(PYRUN) -m pytest tests/unit -v

lint:
	$(PYRUN) -m ruff check shared services

buckets:
	bash scripts/setup_local.sh
