# GKE Auto-Heal Agent - Development Makefile
# Provides commands for MCP-based agent development and testing

.PHONY: help install test clean docs

# Default target
help:
	@echo "GKE Auto-Heal Agent Development Commands"
	@echo "======================================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  install          Install all dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo ""
	@echo "Testing Commands:"
	@echo "  test             Run all tests"
	@echo "  test-integration Run integration tests only"
	@echo "  test-unit        Run unit tests only"
	@echo ""
	@echo "Code Quality Commands:"
	@echo "  lint             Run linting checks"
	@echo "  format           Format code with black and isort"
	@echo "  security         Run security scans"
	@echo ""
	@echo "Documentation Commands:"
	@echo "  docs             Generate and validate documentation"
	@echo "  docs-serve       Serve documentation locally"
	@echo ""
	@echo "Cleanup Commands:"
	@echo "  clean            Clean build artifacts and cache"
	@echo "  clean-all        Clean everything including dependencies"

# Installation targets
install:
	@echo "📦 Installing dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✅ Dependencies installed successfully"

install-dev: install
	@echo "📦 Installing development dependencies..."
	pip install -r requirements-dev.txt
	pip install pre-commit
	pre-commit install
	@echo "✅ Development environment setup complete"

# Testing targets
test: test-unit test-integration
	@echo "✅ All tests completed"

test-unit:
	@echo "🧪 Running unit tests..."
	python -m pytest agents/tests/ -v --ignore=agents/tests/test_integration.py --ignore=agents/tests/test_integration_scenarios.py

test-integration:
	@echo "🧪 Running integration tests..."
	python -m pytest agents/tests/test_integration.py -v

test-security:
	@echo "🧪 Running security compliance tests..."
	python -m pytest agents/tests/test_security_compliance.py -v

# Code quality targets
lint:
	@echo "🔍 Running linting checks..."
	flake8 agents/ --max-line-length=88 --extend-ignore=E203,W503
	pylint agents/ --disable=C0114,C0115,C0116

format:
	@echo "🎨 Formatting code..."
	black agents/
	isort agents/ --profile black

security:
	@echo "🔒 Running security scans..."
	bandit -r agents/ -f txt
	safety check

# Documentation targets
docs:
	@echo "📚 Validating documentation..."
	@if [ ! -f "README.md" ]; then echo "❌ README.md missing"; exit 1; fi
	@if [ ! -f "agents/README.md" ]; then echo "❌ agents/README.md missing"; exit 1; fi
	@echo "✅ Documentation validation passed"

docs-serve:
	@echo "📖 Serving documentation locally..."
	@echo "Main README: file://$(PWD)/README.md"
	@echo "Agents README: file://$(PWD)/agents/README.md"

# Cleanup targets
clean:
	@echo "🧹 Cleaning build artifacts..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -f bandit-report.json safety-report.json

clean-all: clean
	@echo "🧹 Cleaning everything..."
	rm -rf venv/
	rm -rf .venv/

# Development workflow targets
dev-setup: install-dev
	@echo "🚀 Development environment ready!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Run 'make test' to run all tests"
	@echo "2. Run 'make docs' to validate documentation"

pre-commit: format lint test
	@echo "✅ Pre-commit checks completed successfully"

# CI/CD simulation
ci: install-dev test security docs
	@echo "✅ CI pipeline simulation completed successfully"

# Troubleshooting targets
# (No specific troubleshooting targets needed for MCP-based setup)

# Version information
version:
	@echo "📋 Version Information"
	@echo "====================="
	@python --version
	@echo ""
	@echo "📋 Project Structure"
	@echo "==================="
	@find agents/ -name "*.py" -not -path "agents/tests/*" | wc -l | xargs echo "Production Python files:"
	@find agents/tests/ -name "*.py" | wc -l | xargs echo "Test files:"

# Run all agents and web dashboard
run-agents:
	@echo "🚀 Starting all agents and web dashboard..."
	python -m agents.rca_a2a_service &
	python -m agents.remediation_a2a_service &
	python -m agents.audit_a2a_service &
	python -m agents.approval_a2a_service &
	python -m agents.orchestrator_a2a_service &
	python ./web-dashboard/server.py