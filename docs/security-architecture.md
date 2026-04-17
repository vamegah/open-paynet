# Security Architecture

## Secret Loading

`auth-service` and `api-gateway` now support both direct environment variables and `*_FILE` secret mounts for sensitive values.

Required secrets:

- `JWT_SECRET` or `JWT_SECRET_FILE`
- `TOKEN_ISSUER_ADMIN_KEY` or `TOKEN_ISSUER_ADMIN_KEY_FILE`

Optional structured auth config:

- `MERCHANT_CREDENTIALS_JSON` or `MERCHANT_CREDENTIALS_JSON_FILE`
- `SUBJECT_POLICIES_JSON` or `SUBJECT_POLICIES_JSON_FILE`

The active Docker and CI paths expect injected secrets via environment variables or a local `.env` file derived from `infra/docker/.env.example`.

## Kubernetes Secret Management

The active Kubernetes baseline no longer ships a committed live Secret manifest with placeholder values.

Production manifests now expect:

- `ExternalSecret` reconciliation from a `ClusterSecretStore`
- generated target secret `openpaynet-app-secrets`
- cert-manager managed TLS certificate secret `openpaynet-tls`

Reference/example files:

- active external secret: `infra/kubernetes/external-secrets.yaml`
- example secret only for local reference: `infra/kubernetes/secret.example.yaml`
- TLS certificate manifest: `infra/kubernetes/certificate.yaml`

Elasticsearch now also expects an externally sourced `ELASTICSEARCH_PASSWORD` secret for authenticated cluster access.

## Authorization Model

JWTs now carry:

- `role`
- `scopes`
- OAuth2-style `scope` string
- `iss`
- `aud`

JWT issuance is no longer anonymous. `POST /v1/token` now requires the `X-Token-Issuer-Key` header to match the configured token issuer admin secret.

Merchant API keys now resolve to:

- `merchant_id`
- `role`
- `scopes`

## Gateway Enforcement

`POST /v1/payments` now requires:

- role in `payment_initiator`, `merchant`, or `admin`
- scope `payments:write`

When API key auth is used, the gateway also verifies that `merchant_id` in the request matches the merchant bound to the API key.
