# Rollback

## When to Roll Back

Rollback is appropriate when:

- a recent build increases 5xx or latency
- consumers fail after deployment
- release gates fail after promotion
- a service starts but breaks contract or business logic

## Docker Compose Rollback

1. identify the affected service
2. switch back to the last known-good image or compose state
3. recreate only the affected service where possible

Example:

```text
docker compose -f infra/docker/docker-compose.yml up -d --no-deps notification-service
```

## Kubernetes Rollback

For Kubernetes deployments:

```text
kubectl rollout history deployment/api-gateway -n openpaynet
kubectl rollout undo deployment/api-gateway -n openpaynet
```

Repeat for the affected services only.

## Verification After Rollback

1. `python scripts/wait_for_staging.py --timeout-seconds 60`
2. `python scripts/run_tests.py all`
3. `python scripts/check_release_gate.py --prometheus-url http://localhost:19090 --output staging-artifacts/release-gates.json`
4. confirm the original symptom is gone

## If Rollback Is Not Enough

If binaries are restored but data is still inconsistent:

1. pause further writes if possible
2. follow `docs/disaster-recovery.md`
3. verify restore with `scripts/verify_restore.py`
4. rerun regression checks before reopening traffic
