# Operations Runbooks

OpenPayNet now includes a small operator runbook set for live incidents, rollbacks, and recovery.

## Runbooks

- incident response: `docs/incident-response.md`
- rollback: `docs/rollback.md`
- disaster recovery: `docs/disaster-recovery.md`
- staging validation: `docs/staging-deployment.md`
- release gates: `docs/release-gates.md`

## Core Endpoints

- API gateway: `http://localhost:18000/health`
- auth service: `http://localhost:18100/health`
- ledger service: `http://localhost:18200/health`
- notification service: `http://localhost:18300/health`
- Prometheus: `http://localhost:19090`
- Alertmanager: `http://localhost:19093`
- Grafana: `http://localhost:13000`

## First Operator Checks

1. `docker compose -f infra/docker/docker-compose.yml ps`
2. `python scripts/wait_for_staging.py --timeout-seconds 30`
3. `docker compose -f infra/docker/docker-compose.yml logs --no-color`
4. `python scripts/check_release_gate.py --prometheus-url http://localhost:19090 --output staging-artifacts/release-gates.json`
