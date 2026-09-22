.PHONY: help install test run clean venv

# Python version and virtual environment
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help:
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@echo "  $(YELLOW)make help$(NC)        Show this help message"
	@echo "  $(YELLOW)make venv$(NC)        Create virtual environment"
	@echo "  $(YELLOW)make install$(NC)     Install dependencies in venv"
	@echo "  $(YELLOW)make test$(NC)        Run all tests"
	@echo "  $(YELLOW)make run$(NC)         Run the full pipeline"
	@echo "  $(YELLOW)make clean$(NC)       Clean up generated files"

# Create virtual environment
venv:
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✓ Virtual environment created$(NC)"
	@echo ""
	@echo "$(YELLOW)Activate with:$(NC)"
	@echo "  source $(VENV_BIN)/activate"

# Install dependencies
install: venv
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

# Run tests with coverage report
test:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=data_layer --cov=analysis --cov-report=html:tests/htmlcov --cov-report=term
	@echo ""
	@echo "$(GREEN)✓ Coverage report generated at tests/htmlcov/index.html$(NC)"

# Run the full pipeline
run:
	@echo "$(BLUE)Running fund analysis pipeline...$(NC)"
	$(PYTHON) main.py
	@echo ""
	@echo "$(GREEN)✓ Pipeline complete$(NC)"

# Clean up generated files
clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	@rm -f funds_analysis.db
	@rm -rf output/*.csv
	@rm -rf __pycache__
	@rm -rf .pytest_cache
	@rm -rf tests/htmlcov
	@rm -f .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

