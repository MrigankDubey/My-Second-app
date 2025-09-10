# Makefile for Vocabulary Quiz Application

.PHONY: help schema seed docker-up deps api dev test clean

help:
	@echo "Database Setup:"
	@echo "  make schema   - create DB schema (requires psql & createdb)"
	@echo "  make seed     - run Python seeder (requires Python deps)"
	@echo "  make deps     - install Python deps into active venv"
	@echo "  make docker-up - bring up postgres + initializer via docker-compose"
	@echo ""
	@echo "API Development:"
	@echo "  make api      - start FastAPI development server"
	@echo "  make dev      - full development setup (database + API)"
	@echo "  make test     - run API tests"
	@echo "  make clean    - clean up containers and volumes"

schema:
	createdb vocab_app || true
	psql vocab_app -f schema.sql

deps:
	python3 -m pip install -r requirements.txt

seed:
	python3 create_sample_data.py

docker-up:
	docker compose up --build --abort-on-container-exit

api:
	./start-api.sh

dev: docker-up
	@echo "Waiting for database to be ready..."
	@sleep 10
	@echo "Starting API server..."
	@./start-api.sh

test:
	python3 -m pytest tests/ -v

clean:
	docker compose down -v
	docker system prune -f
