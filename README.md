## OpenPayNet

OpenPayNet is a Visa-inspired distributed payments platform being built as an enterprise-grade portfolio project. The current repository is in active implementation and is not production-ready yet.

### Current Focus

- Phase 0/2/3/4 core platform hardening is largely in place
- The tracked backlog is complete and remaining work is now polish, scale, and production-depth refinement

### Services

- `api-gateway`: FastAPI ingress, auth checks, rate limiting, trace propagation
- `auth-service`: JWT issuance and merchant API key validation skeleton
- `payment-service`: payment orchestration consumer
- `fraud-service`: fraud rules consumer
- `ledger-service`: ledger persistence and query API
- `notification-service`: async notification router with delivery query API
- `audit-service`: Elasticsearch audit consumer

### Repo Tracking

- Backlog: `docs/implementation-backlog.md`
- Local stack: `infra/docker/docker-compose.yml`
- local env template: `infra/docker/.env.example`
- Kubernetes baseline: `infra/kubernetes`
- CI skeleton: `.github/workflows/ci-cd.yml`

### Local Observability

- Prometheus: `http://localhost:19090`
- Alertmanager: `http://localhost:19093`
- Grafana: `http://localhost:13000` with credentials from `infra/docker/.env`

### Recovery

- Ledger backup and restore runbook: `docs/disaster-recovery.md`
- operations runbook index: `docs/operations-runbooks.md`
- incident response: `docs/incident-response.md`
- rollback: `docs/rollback.md`
- Windows backup helper: `scripts/ledger_backup.ps1`
- Restore verification utility: `scripts/verify_restore.py`
- Docker ops job: `docker-compose --profile ops -f infra/docker/docker-compose.yml run --rm ledger-backup ...`

### Staging Promotion

- GitHub Actions workflow: `.github/workflows/ci-cd.yml`
- Staging deployment notes: `docs/staging-deployment.md`
- Railway deployment notes: `docs/railway-deployment.md`
- Readiness helper: `scripts/wait_for_staging.py`
- Release gate policy: `docs/release-gates.md`
- Release gate checker: `scripts/check_release_gate.py`

### Contract Testing

- Pact-style payment/ledger contract: `tests/contract-tests/contracts/payment-ledger-contract.json`
- Provider verification test: `tests/contract-tests/test_payment_ledger_contract.py`

### Regression Testing

- Expanded live API coverage: `tests/api-tests/test_payments.py`
- Testcontainers integration smoke: `tests/integration-tests/test_transaction_flow_testcontainers.py`
- Shared test dependencies: `tests/requirements-test.txt`
- bootstrap and runner docs: `docs/test-bootstrap.md`
- fast unit suite: `tests/unit-tests`

### Performance Testing

- k6 load script: `tests/performance-tests/load_test.js`
- k6 summary checker: `scripts/check_k6_summary.py`
- runbook: `docs/performance-testing.md`
- staging workflow runs a k6 smoke and validates the exported summary

### Chaos Testing

- chaos drill runner: `tests/chaos-tests/chaos.py`
- runbook: `docs/chaos-testing.md`

### Security Testing

- OWASP ZAP API scan wrapper: `scripts/run_zap_api_scan.py`
- ZAP report gate: `scripts/check_zap_report.py`
- runbook: `docs/security-testing.md`

### Security Hardening

- secret-loading and mounted secret notes: `docs/security-architecture.md`
- shared runtime config and k8s env layout: `docs/deployment-configuration.md`
- active k8s secret sync now uses `ExternalSecret` instead of a committed live Secret
- ingress TLS is wired for cert-manager via `infra/kubernetes/certificate.yaml`
- Docker Compose and staging now expect injected secrets instead of committed demo values
- JWT issuance now requires the `X-Token-Issuer-Key` admin secret
- JWTs now carry issuer, audience, roles, and OAuth2-style scopes
- merchant API keys now resolve to scoped merchant identities

### Data Privacy

- PCI-aware tokenization and GDPR contact deletion notes: `docs/data-privacy.md`

### Notifications

- async notification routing notes: `docs/notifications.md`
- local notification query endpoint: `http://localhost:18300/v1/notifications/{txn_id}`
