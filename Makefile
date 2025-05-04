.PHONY: setup run build start stop logs backup healthcheck clean setup-docker

# Default target
all: setup

# Setup environment
setup:
	@echo "Creating required directories..."
	mkdir -p logs session backups

# Setup Docker environment
setup-docker:
	@echo "Setting up Docker environment..."
	./setup_docker.sh

# Run locally
run:
	python bot.py

# Docker operations
build:
	docker-compose build

start: setup-docker
	docker-compose up -d

stop:
	docker-compose down

logs:
	docker-compose logs -f

# Maintenance
backup:
	./scripts/backup.sh

healthcheck:
	./healthcheck.py

# Cleanup
clean:
	rm -rf __pycache__
	find . -name "*.pyc" -delete

# Help
help:
	@echo "Available commands:"
	@echo "  make setup       - Create required directories"
	@echo "  make setup-docker - Copy session file to Docker volume"
	@echo "  make run         - Run bot locally (not in Docker)"
	@echo "  make build       - Build Docker image"
	@echo "  make start       - Start Docker container"
	@echo "  make stop        - Stop Docker container"
	@echo "  make logs        - View Docker logs"
	@echo "  make backup      - Backup session files"
	@echo "  make healthcheck - Check if bot is running"
	@echo "  make clean       - Clean up Python cache files" 