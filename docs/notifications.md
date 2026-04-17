# Notification Routing

`notification-service` now routes asynchronous alerts for:

- declined transactions
- approved high-value transactions

Routing behavior:

- declined transactions trigger `email`
- high-value transactions trigger `slack`
- declined high-value transactions trigger both `email` and `slack`

The service stores the latest delivered notification per `txn_id` in Redis and exposes:

```text
GET /v1/notifications/{txn_id}
```

This makes the async notification path directly verifiable in Docker and Kubernetes instead of relying only on container logs.
