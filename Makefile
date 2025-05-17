.DEFAULT_GOAL := help

##@ CI/CD
.PHONY: build
build: ## Build
	uv build

.PHONY: cov
cov: ## Run tests with coverage
	uv run pytest --cov-report=term-missing --cov-config=pyproject.toml --cov=src/plainlog

##@ Quality
.PHONY: test
test: ## Run tests in current Python
	uv run pytest

.PHONY: tests
tests: ## Run tests in all supporte Python versions
	uv run --isolated -p 3.9 pytest
	uv run --isolated -p 3.10 pytest
	uv run --isolated -p 3.11 pytest
	uv run --isolated -p 3.12 pytest
	uv run --isolated -p 3.13 pytest
	uv run --isolated -p 3.14 pytest
	uv run --isolated -p pypy pytest

.PHONY: check
check: ## Run all checks 
	-mypy ./src/plainlog
	ruff check ./src/plainlog

.PHONY: ruff-check
ruff-check: ## Lint using ruff
	ruff check ./src/plainlog

.PHONY: ty-check
ty-check: ## Type check with ty (experimental)
	ty check ./src/plainlog

.PHONY: format
format: ## Format files using black
	ruff format ./src/plainlog

##@ Utility
.PHONY: clean
clean: ## Delete all temporary files
	rm -rf .pytest_cache
	rm -rf **/.pytest_cache
	rm -rf __pycache__
	rm -rf **/__pycache__
	rm -rf build
	rm -rf dist

.PHONY: install
install: ## Install virtual environment
	uv sync

.PHONY: help
help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\033[36m\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
