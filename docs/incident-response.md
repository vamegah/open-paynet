# Incident Response

## Severity

- `SEV-1`: full payment outage, data integrity risk, or unrecoverable request failures
- `SEV-2`: major degradation such as sustained 5xx, consumer stalls, or DLQ growth
- `SEV-3`: partial feature failure with workaround, such as notification-only issues

## Triage

1. capture service state:
   `docker compose -f infra/docker/docker-compose.yml ps`
2. capture readiness:
   `python scripts/wait_for_staging.py --timeout-seconds 30`
3. capture logs:
   `docker compose -f infra/docker/docker-compose.yml logs --no-color > staging-artifacts/incident-logs.txt`
4. inspect Prometheus and Grafana for:
   - gateway 5xx
   - publish failures
   - circuit breaker rejections
   - ledger consumer errors
   - DLQ volume

## Common Cases

### Gateway returning 503 or 504

1. check `api-gateway` logs for Kafka timeout or circuit breaker events
2. verify Kafka and Redis health
3. if recent deploy caused the issue, use the rollback runbook

### Accepted payments not reaching final ledger state

1. inspect `payment-service`, `fraud-service`, and `ledger-service`
2. verify Kafka broker health and consumer progress
3. inspect DLQ topics and ledger error counters
4. verify Postgres health

### Missing notifications

1. check `notification-service` health
2. query `GET /v1/notifications/{txn_id}`
3. verify Redis connectivity
4. confirm the transaction is declined or high-value

## Containment

Use the smallest safe action first:

1. restart a single failed service
2. restart a dependent platform service only if workers cannot recover
3. rollback if tied to a recent change
4. restore from backup if data integrity is in doubt
