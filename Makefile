.PHONY: post-create init sync lint format freeze

# Post-create command: run tool verification, init project, and sync dependencies
post-create: init sync

# Initialize Python environment with uv and create pyproject.toml if needed
init:
	@echo "Initializing Python environment..."
	@(uv python install ${PYTHON_VERSION} && \
	if [ ! -f pyproject.toml ]; then \
		if [ "${UV_INIT_BARE}" = "true" ]; then \
			uv init --bare --python ${PYTHON_VERSION}; \
		else \
			uv init --python ${PYTHON_VERSION}; \
		fi; \
	fi) > /tmp/init.log 2>&1
	@echo "✓ Initialization complete (log: /tmp/init.log)"


# Sync dependencies with uv
sync:
	@echo "Syncing dependencies..."
	@uv sync > /tmp/uv-sync.log 2>&1
	@echo "✓ Dependency sync complete (log: /tmp/uv-sync.log)"
	@echo "Install pre-commit..."
	@uv run pre-commit install > /tmp/pre-commit-install.log 2>&1
	@echo "✓ Pre-commit install complete (log: /tmp/pre-commit-install.log)"

# Run ruff linter
lint:
	@uv run ruff check ./src

# Run ruff formatter
format:
	@uv run ruff format ./src

# Freeze dependencies to tmp folder
freeze:
	@echo "Freezing dependencies..."
	@echo "# Generated on $$(date)" > /tmp/requirements.txt
	@uv pip freeze >> /tmp/requirements.txt
	@echo "✓ Dependencies frozen (log: /tmp/requirements.txt)"
