.PHONY: help up down build test lint format clean logs shell db-shell

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start all services in development mode
	docker-compose up -d

down: ## Stop all services
	docker-compose down

build: ## Build the Docker images
	docker-compose build

rebuild: ## Rebuild the Docker images from scratch
	docker-compose build --no-cache

test: ## Run tests
	docker-compose exec api pytest app/tests/ -v

test-cov: ## Run tests with coverage
	docker-compose exec api pytest app/tests/ -v --cov=app --cov-report=html

lint: ## Run linting
	docker-compose exec api flake8 app/
	docker-compose exec api ruff check app/

format: ## Format code
	docker-compose exec api black app/
	docker-compose exec api ruff format app/

clean: ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f

logs: ## Show logs from all services
	docker-compose logs -f

logs-api: ## Show logs from API service
	docker-compose logs -f api

shell: ## Open a shell in the API container
	docker-compose exec api bash

db-shell: ## Open a PostgreSQL shell
	docker-compose exec db psql -U stellarts -d stellarts_db

dev-setup: ## Initial development setup
	cp env.example .env
	@echo "Please edit .env file with your configuration"
	@echo "Then run: make up"

prod: ## Start production services
	docker-compose up -d api-prod db

migrate: ## Run database migrations
	docker-compose exec api alembic upgrade head

migration: ## Create a new migration (usage: make migration m="description")
	docker-compose exec api alembic revision --autogenerate -m "$(m)"
