.PHONY: setup run build docker-build docker-run docker-compose-up docker-compose-down clean test lint help

# Variables
APP_NAME = check-processing-api
PORT = 8000
PYTHON = python3
PIP = $(PYTHON) -m pip
VENV = .venv
VENV_ACTIVATE = $(VENV)/bin/activate

# Colors for terminal output
CYAN = \033[0;36m
RESET = \033[0m

help:
	@echo "$(CYAN)Check Processing API - Makefile Commands$(RESET)"
	@echo ""
	@echo "$(CYAN)setup$(RESET)              - Install dependencies"
	@echo "$(CYAN)run$(RESET)                - Run the application locally"
	@echo "$(CYAN)build$(RESET)              - Build the application"
	@echo "$(CYAN)docker-build$(RESET)       - Build the Docker image"
	@echo "$(CYAN)docker-run$(RESET)         - Run the application in Docker"
	@echo "$(CYAN)docker-compose-up$(RESET)  - Start the application with Docker Compose"
	@echo "$(CYAN)docker-compose-down$(RESET)- Stop the Docker Compose services"
	@echo "$(CYAN)clean$(RESET)              - Remove build artifacts and Docker containers"
	@echo "$(CYAN)test$(RESET)               - Run tests"
	@echo "$(CYAN)lint$(RESET)               - Run code quality checks"

setup:
	@echo "$(CYAN)Creating virtual environment...$(RESET)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(CYAN)Installing dependencies in virtual environment...$(RESET)"
	. $(VENV_ACTIVATE) && $(PIP) install -r requirements.txt
	@echo "$(CYAN)Setup complete. Activate the virtual environment with:$(RESET)"
	@echo "source $(VENV_ACTIVATE)"

run:
	@echo "$(CYAN)Running application locally on port $(PORT)...$(RESET)"
	uvicorn app:app --host 0.0.0.0 --port $(PORT) --reload

build:
	@echo "$(CYAN)Building application...$(RESET)"
	$(PIP) install -e .

docker-build:
	@echo "$(CYAN)Building Docker image...$(RESET)"
	docker build -t $(APP_NAME) .

docker-run: docker-build
	@echo "$(CYAN)Running Docker container on port $(PORT)...$(RESET)"
	docker run -p $(PORT):$(PORT) \
		-e OPENAI_API_KEY \
		-e AWS_ACCESS_KEY_ID \
		-e AWS_SECRET_ACCESS_KEY \
		-e AWS_REGION \
		$(APP_NAME)

docker-compose-up:
	@echo "$(CYAN)Starting services with Docker Compose...$(RESET)"
	docker-compose up -d

docker-compose-down:
	@echo "$(CYAN)Stopping Docker Compose services...$(RESET)"
	docker-compose down

clean:
	@echo "$(CYAN)Cleaning up...$(RESET)"
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	docker-compose down --rmi local --volumes --remove-orphans 2>/dev/null || true
	docker rmi $(APP_NAME) 2>/dev/null || true

test:
	@echo "$(CYAN)Running tests...$(RESET)"
	pytest

lint:
	@echo "$(CYAN)Running code quality checks...$(RESET)"
	flake8 .
	black --check . 