bash: start				# Run bash inside `main` container
	docker compose run --rm -it main bash

build:					# Build containers
	docker compose build

clean: stop				# Stop and clean orphan containers
	docker compose down -v --remove-orphans

help:					# List all make commands
	@awk -F ':.*#' '/^[a-zA-Z_-]+:.*?#/ { printf "\033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST) | sort

kill:					# Force stop (kill) and remove containers
	docker compose kill
	docker compose rm --force

lint:					# Run linter script
	docker compose run --rm -it main /app/lint.sh

logs:					# Show all containers' logs (tail)
	docker compose logs -tf

restart: stop start		# Stop all containers and start all containers in background

run: start				# Run main ETL script
	docker compose run --rm -it main bash -c "cd /app && ./run.sh"

start:					# Start all containers in background
	UID=$${UID:-1000}
	GID=$${UID:-1000}
	mkdir -p docker/data/main docker/data/db
	chown -R $$UID:$$GID docker/data/main docker/data/db
	touch docker/env/main.local docker/env/db.local
	docker compose up -d

stop:					# Stop all containers
	docker compose down

.PHONY: bash build clean help kill lint logs restart run start stop
