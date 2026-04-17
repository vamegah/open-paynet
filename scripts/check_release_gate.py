import argparse
import json
import math
import sys
import urllib.parse
import urllib.request


DEFAULT_PROMETHEUS_URL = "http://localhost:19090"

GATES = [
    {
        "name": "gateway_p99_latency_seconds",
        "query": 'histogram_quantile(0.99, sum by (le) (rate(openpaynet_gateway_request_latency_seconds_bucket{path="/v1/payments",method="POST"}[5m])))',
        "threshold": 0.3,
        "comparison": "lte",
        "description": "p99 latency for POST /v1/payments must stay below 300ms",
    },
    {
        "name": "gateway_5xx_error_rate",
        "query": '(sum(rate(openpaynet_gateway_requests_total{status=~"5.."}[5m])) / clamp_min(sum(rate(openpaynet_gateway_requests_total[5m])), 0.001))',
        "threshold": 0.01,
        "comparison": "lte",
        "description": "gateway 5xx rate must stay below 1%",
    },
    {
        "name": "gateway_publish_failures_10m",
        "query": "increase(openpaynet_gateway_payment_events_failed_total[10m])",
        "threshold": 0.0,
        "comparison": "lte",
        "description": "payment publish failures must be zero in staging",
    },
    {
        "name": "gateway_circuit_breaker_rejections_10m",
        "query": "increase(openpaynet_gateway_payment_circuit_breaker_rejections_total[10m])",
        "threshold": 0.0,
        "comparison": "lte",
        "description": "circuit breaker rejections must be zero in staging",
    },
    {
        "name": "ledger_consumer_errors_10m",
        "query": "increase(openpaynet_ledger_consumer_errors_total[10m])",
        "threshold": 0.0,
        "comparison": "lte",
        "description": "ledger consumer errors must be zero in staging",
    },
    {
        "name": "ledger_dlq_publishes_10m",
        "query": "increase(openpaynet_ledger_dlq_publishes_total[10m])",
        "threshold": 0.0,
        "comparison": "lte",
        "description": "ledger DLQ publishes must be zero in staging",
    },
]


def query_prometheus(base_url: str, query: str) -> float:
    url = f"{base_url}/api/v1/query?{urllib.parse.urlencode({'query': query})}"
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    results = payload.get("data", {}).get("result", [])
    if not results:
        return 0.0
    value = float(results[0]["value"][1])
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return value


def compare(value: float, threshold: float, mode: str) -> bool:
    if mode == "lte":
        return value <= threshold
    raise ValueError(f"Unsupported comparison mode: {mode}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate release gates from Prometheus metrics.")
    parser.add_argument("--prometheus-url", default=DEFAULT_PROMETHEUS_URL)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    report = {"status": "passed", "gates": []}

    for gate in GATES:
        value = query_prometheus(args.prometheus_url, gate["query"])
        passed = compare(value, gate["threshold"], gate["comparison"])
        report["gates"].append(
            {
                "name": gate["name"],
                "description": gate["description"],
                "query": gate["query"],
                "value": value,
                "threshold": gate["threshold"],
                "comparison": gate["comparison"],
                "passed": passed,
            }
        )
        if not passed:
            report["status"] = "failed"

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
