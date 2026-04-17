# Security Testing

OpenPayNet includes an OWASP ZAP API scan for the API gateway.

## What It Covers

- imports the gateway OpenAPI schema from `/openapi.json`
- sends the merchant API key header so authenticated endpoints are exercised
- exports JSON, HTML, and Markdown reports
- fails the gate on `medium` or `high` findings by default

## Local Run

Make sure the Docker stack is already up, then run:

```powershell
python .\scripts\run_zap_api_scan.py --docker-network docker_default --openapi-url http://api-gateway:8000/openapi.json --output-dir .\staging-artifacts
```

Validate the JSON report:

```powershell
python .\scripts\check_zap_report.py --report .\staging-artifacts\zap-api-scan.json --fail-on-risk medium --output .\staging-artifacts\zap-summary.json
```

## Outputs

- `staging-artifacts/zap-api-scan.json`
- `staging-artifacts/zap-api-scan.html`
- `staging-artifacts/zap-api-scan.md`
- `staging-artifacts/zap-summary.json`

## CI Behavior

The staging workflow runs the ZAP API scan against the Compose network and uploads the raw report plus the parsed summary as build artifacts.
