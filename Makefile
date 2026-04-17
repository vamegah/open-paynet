.PHONY: up down bootstrap-test-env test integration-test clean

up:
	docker-compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up --build -d
	sleep 10  # wait for Kafka

down:
	docker-compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml down

bootstrap-test-env:
	python scripts/bootstrap_test_env.py

integration-test:
	python scripts/run_tests.py integration

test: integration-test

clean:
	docker-compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml down -v
