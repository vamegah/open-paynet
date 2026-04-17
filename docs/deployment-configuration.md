# Deployment Configuration

## Shared Runtime Configuration

OpenPayNet now uses a shared Python helper in `shared/config.py` for:

- environment flag parsing
- integer and float env parsing
- `_FILE`-based secret loading
- JSON config loading
- OAuth scope parsing
- legacy merchant API key parsing

This keeps gateway, auth, and worker services on the same config-loading behavior in local Docker and Kubernetes.

## Kubernetes Baseline

The Kubernetes baseline lives in `infra/kubernetes` and is organized as:

- `namespace.yaml`
- `configmap.yaml`
- `external-secrets.yaml`
- `certificate.yaml`
- `platform.yaml`
- `apps.yaml`
- `poddisruptionbudgets.yaml`
- `ingress.yaml`
- `kustomization.yaml`

Apply it with:

```text
kubectl apply -k infra/kubernetes
```

## Config Separation

`configmap.yaml` holds non-secret shared runtime settings such as:

- Kafka bootstrap address
- Redis URL
- database URL
- Elasticsearch URL
- retry and timeout settings
- fraud rule thresholds

`external-secrets.yaml` defines the active secret sync for sensitive values such as:

- `JWT_SECRET`
- `TOKENIZATION_SECRET`
- merchant credential JSON
- subject policy JSON
- Postgres credentials
- Elasticsearch password

`secret.example.yaml` is now only a reference file for local bootstrap or operator onboarding and should not be applied as-is in production.

## Docker Compose Secrets

The local Docker stack no longer carries committed runtime secrets.

Create a local env file from:

```text
infra/docker/.env.example
```

and pass it explicitly when running Compose from the repo root:

```text
docker compose --env-file infra/docker/.env -f infra/docker/docker-compose.yml up --build -d
```

and provide values for:

- `JWT_SECRET`
- `TOKENIZATION_SECRET`
- `MERCHANT_CREDENTIALS_JSON`
- `POSTGRES_PASSWORD`
- Grafana admin credentials

GitHub Actions staging now expects the same values via repository or environment secrets.

## TLS

Ingress now expects cert-manager to provision TLS for `openpaynet.local` using:

- `infra/kubernetes/certificate.yaml`
- `infra/kubernetes/ingress.yaml`

The ingress forces HTTPS redirect and references the managed certificate secret `openpaynet-tls`.

## HA Baseline

The Kubernetes platform baseline is now more production-shaped:

- Kafka moved to a 3-replica KRaft StatefulSet
- Elasticsearch moved to a 3-replica authenticated StatefulSet
- Redis and Postgres remain stateful with PVC-backed storage
- PodDisruptionBudgets protect app replicas during voluntary disruptions
