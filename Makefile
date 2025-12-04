# Makefile for IKC MCP Server Development

# Use .ONESHELL to allow for multiline shell commands in a single rule
.ONESHELL:

# Define python and pip interpreters dynamically
PYTHON := $(shell command -v python3 || command -v python)
PIP := $(shell command -v pip3 || command -v pip)
PROJECT_NAME := ibm-watsonx-data-intelligence-mcp-server

# Self-documenting help target. See https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

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
