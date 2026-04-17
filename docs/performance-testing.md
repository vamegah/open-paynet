# Performance Testing

## k6 Profiles

OpenPayNet includes a k6-based load script at `tests/performance-tests/load_test.js`.

Supported profiles:

- `smoke`: lightweight staging-friendly check
- `sustained`: longer local run for throughput and latency observation

## Local Execution

If `k6` is installed locally:

```powershell
k6 run tests/performance-tests/load_test.js
```

Using Docker against the Compose network:

```powershell
Get-Content tests\performance-tests\load_test.js -Raw | docker run -i --rm --network docker_default -v "${PWD}:/work" -w /work -e API_GATEWAY_URL=http://api-gateway:8000 -e AUTH_URL=http://auth-service:8100 grafana/k6:0.49.0 run -
```

Run a sustained profile:

```powershell
$env:K6_PROFILE="sustained"
Get-Content tests\performance-tests\load_test.js -Raw | docker run -i --rm --network docker_default -v "${PWD}:/work" -w /work -e API_GATEWAY_URL=http://api-gateway:8000 -e AUTH_URL=http://auth-service:8100 -e K6_PROFILE=$env:K6_PROFILE grafana/k6:0.49.0 run -
```

## Summary Export

You can export a JSON summary and evaluate it with the checker:

```powershell
Get-Content tests\performance-tests\load_test.js -Raw | docker run -i --rm --network docker_default -v "${PWD}:/work" -w /work -e API_GATEWAY_URL=http://api-gateway:8000 -e AUTH_URL=http://auth-service:8100 -e K6_SUMMARY_EXPORT=/work/k6-summary.json grafana/k6:0.49.0 run -
```

Then validate:

```powershell
python .\scripts\check_k6_summary.py --summary .\k6-summary.json
```

## Targets

- smoke profile: p95 under `500ms`, failed request rate under `1%`
- sustained profile: p95 under `300ms`, failed request rate under `1%`

These thresholds are for the current portfolio environment, not the final Visa-scale target.

The script intentionally rotates authenticated subjects and `user_id` values on each iteration so the performance test simulates many independent users instead of tripping the gateway and fraud velocity controls.
