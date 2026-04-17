# Staging Deployment

## Deployment Model

OpenPayNet uses an ephemeral staging promotion workflow in GitHub Actions.

The staging job:

1. Builds the Docker images from the current branch tip.
2. Starts the full local topology with Docker Compose.
3. Waits for the staging endpoints to become reachable.
4. Runs the API and integration regression suite against the live stack.
5. Evaluates release gates from Prometheus metrics.
6. Publishes logs and deployment metadata as workflow artifacts.
7. Tears the environment down after the run completes.

## Workflow Trigger

- Automatic on pushes to `main` or `master`
- Manual via `workflow_dispatch`

## Environment

- GitHub Actions environment: `staging`
- Compose project name: `openpaynet-staging`

## Readiness Checks

The workflow waits for:

- `auth-service` health
- `api-gateway` health
- `ledger-service` health
- Prometheus readiness
- Grafana login page reachability

The readiness helper lives in `scripts/wait_for_staging.py`.

## Deployment Evidence

Each staging run uploads:

- `compose-ps.txt`
- `compose-logs.txt`
- `readiness.json`
- `release-gates.json`

These artifacts can be used to troubleshoot failed promotions.
