# Makefile for IKC MCP Server Development

# Use .ONESHELL to allow for multiline shell commands in a single rule
.ONESHELL:

# Define python and pip interpreters dynamically
PYTHON := $(shell command -v python3 || command -v python)
PIP := $(shell command -v pip3 || command -v pip)
PROJECT_NAME := ibm-data-intelligence-mcp-server

# Self-documenting help target. See https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Service Management
# ==============================================================================

.PHONY: service-list
service-list: ## List all available services and their tools.
	@$(PYTHON) scripts/manage.py service list

.PHONY: service-create
service-create: ## Create a new service. Args: name (e.g., make service-create name=my_new_service)
	@if [ -z "$(name)" ]; then \
		echo "Error: 'name' argument is required."; \
		echo "Usage: make service-create name=<your_service_name>"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/manage.py service create $(name)

.PHONY: service-add-tool
service-add-tool: ## Add a new tool to an existing service. Args: service, tool (e.g., make service-add-tool service=my_service tool=my_tool)
	@if [ -z "$(service)" ] || [ -z "$(tool)" ]; then \
		echo "Error: 'service' and 'tool' arguments are required."; \
		echo "Usage: make service-add-tool service=<service_name> tool=<tool_name>"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/manage.py service add-tool $(service) $(tool)

# ==============================================================================
# Server Operations
# ==============================================================================

.PHONY: run
run: ## Sets up venv, installs deps, and runs the MCP server.
	@echo "--> Setting up virtual environment with uv..."
	@uv venv
	@echo "--> Installing all dependencies (including dev)..."
	@uv pip install -e .[dev]
	@echo "--> Running server..."
	@uv run python -m app.main

.PHONY: run-https
run-https: ## Sets up venv, installs deps, and runs the MCP server with HTTPS.
	@echo "--> Setting up virtual environment with uv..."
	@uv venv
	@echo "--> Installing all dependencies (including dev)..."
	@uv pip install -e .[dev]
	@echo "--> Checking for SSL certificate and key..."
	@if [ ! -f ./server.crt ] || [ ! -f ./server.key ]; then \
		echo "--> Generating self-signed certificate and key..."; \
		openssl genrsa -out server.key 2048; \
		openssl req -new -key server.key -out server.csr -subj "/CN=localhost"; \
		openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt; \
		rm -f server.csr; \
		chmod 600 server.key; \
		chmod 644 server.crt; \
		echo "--> Self-signed certificate and key generated successfully."; \
	fi
	@echo "--> Running server with https..."
	@uv run python -m app.main --ssl-cert ./server.crt --ssl-key ./server.key

.PHONY: run-stdio
run-stdio: ## Sets up venv, installs deps, and runs the MCP server in stdio mode.
	@echo "--> Setting up virtual environment with uv..."
	@uv venv
	@echo "--> Syncing dependencies with uv..."
	@uv sync
	@echo "--> Running server in stdio mode..."
	@uv run python -m app.main --transport stdio

# ==============================================================================
# Code Quality
# ==============================================================================

.PHONY: lint
lint: ## Run the linter to check for style issues and errors.
	@uv run ruff check .

.PHONY: lint-fix
lint-fix: ## Run the linter and automatically fix issues.
	@uv run ruff check . --fix

# ==============================================================================
# Testing
# ==============================================================================

.PHONY: test
test: ## Run all unit tests
	@echo "--> Installing uv if not available..."
	@if ! command -v uv >/dev/null 2>&1; then \
		if command -v pip3 >/dev/null 2>&1; then \
			pip3 install uv; \
			export PATH="$$HOME/.local/bin:$$PATH"; \
		elif command -v pip >/dev/null 2>&1; then \
			pip install uv; \
			export PATH="$$HOME/.local/bin:$$PATH"; \
		else \
			echo "Error: Neither pip3 nor pip found. Cannot install uv."; \
			exit 1; \
		fi; \
	fi
	@echo "--> Installing test dependencies..."
	@uv sync --group test
	@echo "--> Running unit tests with coverage..."
	@uv run python -m pytest tests/ --cov=. --cov-report=xml --cov-report=term-missing

.PHONY: test-generate-tool
test-generate-tool: ## Generate test stub for specific tool. Args: service, tool (e.g., make test-generate-tool service=dummy tool=lineage)
	@if [ -z "$(service)" ] || [ -z "$(tool)" ]; then \
		echo "Error: 'service' and 'tool' arguments are required."; \
		echo "Usage: make test-generate-tool service=<service_name> tool=<tool_name>"; \
		exit 1; \
	fi
	@echo "--> Generating test stub for $(service):$(tool)"
	@$(PYTHON) scripts/manage.py test generate --service $(service) --tool $(tool)

# ==============================================================================
# Client Operations
# ==============================================================================

.PHONY: run-client
run-client: ## Sets up venv, installs all deps, and runs the Ollama client.
	@echo "--> Setting up virtual environment with uv..."
	@uv venv
	@echo "--> Installing all dependencies (including dev)..."
	@uv pip install -e .[dev]
	@echo "--> Running simple MCP client..."
	@.venv/bin/python -m client.simple_client

# ==============================================================================
# 📦 PACKAGING & PUBLISHING
# ==============================================================================

.PHONY: clean
clean: ## Remove build artifacts and cache files
	@echo "--> Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info/ .eggs/
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

.PHONY: dist
dist: clean ## Build wheel + sdist into ./dist
	@echo "--> Building wheel and source distribution..."
	@uv run python -m build
	@echo "🛠  Wheel & sdist written to ./dist"

.PHONY: wheel
wheel: clean ## Build wheel only
	@echo "--> Building wheel..."
	@uv run python -m build --wheel
	@echo "🛠  Wheel written to ./dist"

.PHONY: sdist
sdist: clean ## Build source distribution only
	@echo "--> Building source distribution..."
	@uv run python -m build --sdist
	@echo "🛠  Source distribution written to ./dist"

.PHONY: verify
verify: dist ## Build, run twine check (no upload)
	@echo "--> Verifying package..."
	@uv run twine check dist/*
	@echo "✅  Package verified - ready to publish."

.PHONY: install-local
install-local: wheel ## Build wheel and install locally for testing
	@if [ -z "$(PYTHON)" ]; then \
		echo "Error: python3 or python not found in PATH. Please install it."; \
		exit 1; \
	fi
	@echo "--> Installing locally from wheel..."
	@uv pip install --force-reinstall dist/*.whl
	@echo "✅  Package installed locally - you can now use 'data-intelligence-mcp-server' command"

.PHONY: install-global
install-global: wheel ## Build wheel and install globally with pip (system-wide)
	@if [ -z "$(PIP)" ]; then \
		echo "Error: pip3 or pip not found in PATH. Please install it."; \
		exit 1; \
	fi
	@echo "--> Installing globally with $(PIP)..."
	@$(PIP) install --force-reinstall --break-system-packages dist/*.whl
	@echo "✅  Package installed globally - 'data-intelligence-mcp-server' command available system-wide"

.PHONY: install-dev
install-dev: ## Install in editable/development mode
	@if [ -z "$(PYTHON)" ]; then \
		echo "Error: python3 or python not found in PATH. Please install it."; \
		exit 1; \
	fi
	@echo "--> Installing in editable mode..."
	@uv pip install -e .[dev]
	@echo "✅  Package installed in development mode"

.PHONY: publish
publish: verify ## Verify, then upload to PyPI
	@echo "--> Publishing to PyPI..."
	@uv run twine upload dist/*
	@echo "  Upload finished - check https://pypi.org/project/$(PROJECT_NAME)/"

.PHONY: publish-testpypi
publish-testpypi: verify ## Verify, then upload to TestPyPI
	@echo "--> Publishing to TestPyPI..."
	@uv run twine upload --repository testpypi dist/*
	@echo "  Upload finished - check https://test.pypi.org/project/$(PROJECT_NAME)/"
