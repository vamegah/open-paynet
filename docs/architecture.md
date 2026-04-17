# OpenPayNet Architecture

## Target Flow

1. Client calls `api-gateway` with JWT or merchant API key plus `idempotency_key`.
2. API gateway generates or propagates `trace_id`.
3. Payment request is published to Kafka with trace and idempotency metadata.
4. `payment-service` performs payment orchestration and emits a processed event.
5. `fraud-service` evaluates rules and emits a fraud decision.
6. `ledger-service` stores the immutable record and exposes query APIs.
7. `notification-service` reacts asynchronously to high-value or failed events and persists routed delivery records.
8. `audit-service` ships all relevant state changes into Elasticsearch.

## Current State

- The repository now contains a starter implementation for trace propagation, idempotency storage, a ledger query API, and a missing auth service skeleton.
- The Docker stack now includes Prometheus, Alertmanager, and Grafana with starter dashboards and alert rules.
- The gateway publish path now has timeout and circuit-breaker protection, and the async workers use retries plus DLQ handling.
- Chaos, performance, security, and deeper recovery work are still tracked in the backlog.
