# Release Gates

## Staging SLOs

OpenPayNet uses the staging environment as the pre-release gate for service-level objectives.

### Release Criteria

1. `POST /v1/payments` p99 latency over the staging verification window must be below `300ms`.
2. Gateway `5xx` error rate over the staging verification window must stay below `1%`.
3. Gateway payment event publish failures over `10m` must be `0`.
4. Gateway circuit-breaker rejections over `10m` must be `0`.
5. Ledger consumer errors over `10m` must be `0`.
6. Ledger DLQ publishes over `10m` must be `0`.
7. Contract, API, and integration suites must pass in staging.
8. Staging readiness checks must succeed for auth, gateway, ledger, Prometheus, and Grafana.

## Metrics Mapping

| Objective | Prometheus Query |
|---|---|
| p99 latency | `histogram_quantile(0.99, sum by (le) (rate(openpaynet_gateway_request_latency_seconds_bucket{path="/v1/payments",method="POST"}[5m])))` |
| 5xx rate | `(sum(rate(openpaynet_gateway_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(openpaynet_gateway_requests_total[5m])), 0.001))` |
| Publish failures | `increase(openpaynet_gateway_payment_events_failed_total[10m])` |
| Circuit-breaker rejections | `increase(openpaynet_gateway_payment_circuit_breaker_rejections_total[10m])` |
| Ledger consumer errors | `increase(openpaynet_ledger_consumer_errors_total[10m])` |
| Ledger DLQ activity | `increase(openpaynet_ledger_dlq_publishes_total[10m])` |

## Automation

The staging workflow evaluates these gates with:

```text
python scripts/check_release_gate.py --prometheus-url http://localhost:19090
```

The resulting report is uploaded as a workflow artifact.

## Notes

- These are release gates for the current portfolio implementation, not final production SLO commitments.
- The long-term Visa-aligned target remains five-nines availability with stricter latency and throughput validation under dedicated performance and chaos suites.
