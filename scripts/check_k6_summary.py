import argparse
import json
import sys
from pathlib import Path


def read_metric(summary: dict, name: str) -> dict:
    metrics = summary.get("metrics", {})
    if name not in metrics:
        raise KeyError(f"Metric {name} not found in k6 summary")
    return metrics[name]


def metric_value(metric: dict, key: str, default: float = 0.0) -> float:
    if "values" in metric:
        return float(metric["values"].get(key, default))
    return float(metric.get(key, default))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate exported k6 summary metrics.")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--max-payment-p95-ms", type=float, default=500.0)
    parser.add_argument("--max-failed-rate", type=float, default=0.01)
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        raise FileNotFoundError(f"k6 summary file not found: {summary_path}")

    with summary_path.open("r", encoding="utf-8") as handle:
        summary = json.load(handle)

    payment_duration = read_metric(summary, "http_req_duration{endpoint:payments}")
    payment_failures = read_metric(summary, "http_req_failed{endpoint:payments}")

    p95 = metric_value(payment_duration, "p(95)")
    failed_rate = metric_value(payment_failures, "rate", metric_value(payment_failures, "value"))

    report = {
        "status": "passed",
        "payment_p95_ms": p95,
        "payment_failed_rate": failed_rate,
        "limits": {
            "max_payment_p95_ms": args.max_payment_p95_ms,
            "max_failed_rate": args.max_failed_rate,
        },
    }

    if p95 > args.max_payment_p95_ms or failed_rate > args.max_failed_rate:
        report["status"] = "failed"

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
