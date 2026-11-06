# Makefile for IKC MCP Server Development

# Use .ONESHELL to allow for multiline shell commands in a single rule
.ONESHELL:

# Abort a recipe on the first failing command (otherwise a failed build is masked by later echo lines)
.SHELLFLAGS := -e -c

# Release tooling (build, twine) lives in the "release" dependency group, which uv does not install by default
UV_RELEASE := uv run --group release

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
	@$(UV_RELEASE) python -m build
	@echo "🛠  Wheel & sdist written to ./dist"

.PHONY: wheel
wheel: clean ## Build wheel only
	@echo "--> Building wheel..."
	@$(UV_RELEASE) python -m build --wheel
	@echo "🛠  Wheel written to ./dist"

.PHONY: sdist
sdist: clean ## Build source distribution only
	@echo "--> Building source distribution..."
	@$(UV_RELEASE) python -m build --sdist
	@echo "🛠  Source distribution written to ./dist"

.PHONY: verify
verify: dist ## Build, run twine check (no upload)
	@echo "--> Verifying package..."
	@$(UV_RELEASE) twine check dist/*
	@echo "✅  Package verified - ready to publish."

.PHONY: publish
publish: verify ## Verify, then upload to PyPI
	@echo "--> Publishing to PyPI..."
	@$(UV_RELEASE) twine upload dist/*
	@echo "  Upload finished - check https://pypi.org/project/$(PROJECT_NAME)/"

.PHONY: publish-testpypi
publish-testpypi: verify ## Verify, then upload to TestPyPI
	@echo "--> Publishing to TestPyPI..."
	@$(UV_RELEASE) twine upload --repository testpypi dist/*
	@echo "  Upload finished - check https://test.pypi.org/project/$(PROJECT_NAME)/"
