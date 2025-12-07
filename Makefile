PYTHON ?= python3.13
VENV ?= .venv

.PHONY: help venv dev-install lint format typecheck pre-commit-install addon-build

help: ## Show this help message
	@printf "Home Assistant Moonshine add-ons repo\n"
	@printf "Usage: make [target]\n\n"
	@printf "Available targets:\n"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		sed -E 's/^([a-zA-Z0-9_-]+):.*?## (.*)$$/  \1\t\2/'

venv: ## Create local Python virtualenv for tooling (no moonshine_onnx runtime deps)
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip && pip install -r requirements-dev.txt

dev-install: venv ## Ensure venv exists and dev tools installed

lint: ## Run ruff linting
	. $(VENV)/bin/activate && ruff check .

format: ## Run ruff formatter
	. $(VENV)/bin/activate && ruff format .

typecheck: ## Run mypy type checking
	. $(VENV)/bin/activate && mypy wyoming-moonshine/wyoming_moonshine

pre-commit-install: ## Install pre-commit hooks
	. $(VENV)/bin/activate && pre-commit install

addon-build: ## Build the wyoming-moonshine add-on image locally
	cd wyoming-moonshine && docker build --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest -t wyoming-moonshine-addon:local .
