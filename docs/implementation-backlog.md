# OpenPayNet Implementation Backlog

Status values:

- `todo`
- `in-progress`
- `done`
- `blocked`

## Phase 0: Foundation

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P0-01 | done | Repo hygiene | Replace placeholder docs with project status and architecture summaries | Non-empty `README` and docs |
| P0-02 | done | Delivery pipeline | Create a starter GitHub Actions workflow | `.github/workflows/ci-cd.yml` |
| P0-03 | done | Local environment | Expand Docker Compose to include auth, ledger, audit, notification, Postgres, and Elasticsearch | Runnable local topology |
| P0-04 | done | Service entrypoints | Add missing `main.py` wrappers for worker services | Importable service entrypoints |
| P0-05 | done | Kubernetes | Add deployment, service, probe, and resource-limit manifests for all services | `infra/kubernetes/*` |
| P0-06 | done | Config | Centralize environment variables and secret loading strategy | Shared config module |
| P0-07 | done | Verification | Repair local Python execution path so tests can run in CI and local dev | Working Python test bootstrap |

## Phase 1: Core Payment Contract

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P1-01 | done | Auth | Add missing auth service skeleton for JWT issuance and merchant API key validation | `services/auth-service` |
| P1-02 | done | Traceability | Propagate `trace_id` from gateway into payment events and responses | HTTP + Kafka trace metadata |
| P1-03 | done | Idempotency | Add `idempotency_key` to payment contract and cache same-response replay in gateway | Redis-backed gateway skeleton |
| P1-04 | done | Ledger | Add a ledger query API and richer transaction schema | `GET /v1/ledger/{txn_id}` |
| P1-05 | done | Payment contract | Add payment type, merchant metadata, and structured response payloads | Shared request/response shape |
| P1-06 | done | Acceptance path | Implement true accepted vs declined orchestration and error mapping | End-to-end status lifecycle |
| P1-07 | done | Fraud | Add geo mismatch and IP reputation rules | Expanded fraud engine |
| P1-08 | done | Notifications | Trigger alerts for failed or high-value transactions | Notification routing logic |

## Phase 2: Security and Compliance

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P2-01 | done | Security | Replace default secrets and wire secret management | Secret loading path |
| P2-02 | done | PCI awareness | Simulate tokenization and forbid PAN storage | Tokenization module |
| P2-03 | done | GDPR | Implement deletion workflow for personal contact data | Delete API + retention policy |
| P2-04 | done | AuthZ | Add OAuth2 scopes and merchant role checks | Scope-aware auth |

## Phase 3: Resilience and Operability

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P3-01 | done | Messaging | Add retries, DLQs, and replay-safe consumers | Durable async processing |
| P3-02 | done | Resilience | Add circuit breakers and timeout policies | Safe failure modes |
| P3-03 | done | Observability | Emit structured JSON logs, metrics, and alerts | Prometheus/Grafana baseline |
| P3-04 | done | Recovery | Add Postgres backup and restore scripts | `pg_dump` workflow |
| P3-05 | done | Startup hardening | Add explicit Kafka topic provisioning and compose-level readiness gates for Kafka and Elasticsearch before dependent services start | Stable Docker bootstrap |

## Phase 4: Test Automation

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P4-01 | done | Unit | Add fraud, idempotency, and ledger unit tests | Fast deterministic suite |
| P4-02 | done | API | Cover auth, validation, idempotency, and ledger query APIs | API regression suite |
| P4-03 | done | Contract | Add Pact between payment and ledger | Consumer/provider contracts |
| P4-04 | done | Integration | Use Testcontainers for Kafka, Redis, Postgres, Elasticsearch | Reliable integration harness |
| P4-05 | done | Performance | Add k6 smoke and sustained load tests | Latency/throughput reports |
| P4-06 | done | Chaos | Add service kill and broker outage drills | Chaos scripts |
| P4-07 | done | Security | Add OWASP ZAP checks against the gateway | Security scan stage |

## Phase 5: Release Readiness

| ID | Status | Requirement Area | Task | Deliverable |
|---|---|---|---|---|
| P5-01 | done | Staging | Add deploy-to-staging workflow | Environment promotion |
| P5-02 | done | SLOs | Define p99, error-rate, and availability objectives | Runbook + alerts |
| P5-03 | done | Operations | Add incident, rollback, and recovery runbooks | Ops docs |
