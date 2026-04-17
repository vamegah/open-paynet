# Railway Deployment

## Recommended Test Slice

For the fastest Railway test deployment, deploy these services:

- `api-gateway`
- `auth-service`
- `payment-service`
- `fraud-service`
- `ledger-service`
- `notification-service`
- Railway `PostgreSQL`
- Railway `Redis`
- Railway `Kafka`

Skip these on the first pass:

- `audit-service`
- Elasticsearch
- Prometheus
- Alertmanager
- Grafana
- ZooKeeper

## Why

Railway does not run `docker-compose.yml` directly. Each Compose service must be deployed as its own Railway service. Private networking is automatic, and services can communicate over `service-name.railway.internal`.

## Service Setup

Create one Railway service per app service, all pointing at the same repo.

Set `RAILWAY_DOCKERFILE_PATH` per service:

- `services/api-gateway/Dockerfile`
- `services/auth-service/Dockerfile`
- `services/payment-service/Dockerfile`
- `services/fraud-service/Dockerfile`
- `services/ledger-service/Dockerfile`
- `services/notification-service/Dockerfile`

Public service:

- `api-gateway`

Private services:

- `auth-service`
- `payment-service`
- `fraud-service`
- `ledger-service`
- `notification-service`

## Key Variables

Shared across services:

- `JWT_SECRET`
- `TOKEN_ISSUER_ADMIN_KEY`
- `JWT_ISSUER=openpaynet-auth`
- `JWT_AUDIENCE=openpaynet-api`
- `TOKENIZATION_SECRET`
- `MERCHANT_CREDENTIALS_JSON`
- `SUBJECT_POLICIES_JSON`

`api-gateway`:

- `HOST=::`
- `PORT=8000`
- `KAFKA_BOOTSTRAP_SERVERS=kafka.railway.internal:9092`
- `REDIS_URL=${{Redis.REDIS_URL}}`

`auth-service`:

- `HOST=::`
- `PORT=8100`

`payment-service`:

- `KAFKA_BOOTSTRAP_SERVERS=kafka.railway.internal:9092`

`fraud-service`:

- `KAFKA_BOOTSTRAP_SERVERS=kafka.railway.internal:9092`
- `REDIS_URL=${{Redis.REDIS_URL}}`

`ledger-service`:

- `HOST=::`
- `PORT=8200`
- `KAFKA_BOOTSTRAP_SERVERS=kafka.railway.internal:9092`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`

`notification-service`:

- `HOST=::`
- `PORT=8300`
- `KAFKA_BOOTSTRAP_SERVERS=kafka.railway.internal:9092`
- `REDIS_URL=${{Redis.REDIS_URL}}`

## Notes

- Railway does not support Compose `depends_on`; services must tolerate dependency startup timing.
- `api-gateway`, `auth-service`, `ledger-service`, and `notification-service` now honor `HOST` and `PORT`.
- Use Railway PostgreSQL and Redis templates instead of self-hosting them inside the app repo.
- If you need a public ledger endpoint for testing, you can temporarily expose `ledger-service`, but keeping only `api-gateway` public is cleaner.
