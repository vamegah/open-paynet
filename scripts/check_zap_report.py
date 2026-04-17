import argparse
import json
import sys
from pathlib import Path


RISK_LABELS = {
    "0": "informational",
    "1": "low",
    "2": "medium",
    "3": "high",
}


def iter_alerts(report: dict):
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            yield alert


def normalize_risk(alert: dict) -> tuple[int, str]:
    raw = str(alert.get("riskcode", "0"))
    try:
        risk_code = int(raw)
    except ValueError:
        risk_code = 0
    return risk_code, RISK_LABELS.get(str(risk_code), "informational")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a ZAP JSON report and fail on configured severities.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--fail-on-risk", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--output", help="Optional JSON summary output path.")
    args = parser.parse_args()

    threshold_map = {"low": 1, "medium": 2, "high": 3}
    fail_threshold = threshold_map[args.fail_on_risk]

    with open(args.report, "r", encoding="utf-8") as handle:
        report = json.load(handle)

    findings = []
    counts = {"informational": 0, "low": 0, "medium": 0, "high": 0}
    for alert in iter_alerts(report):
        risk_code, risk_label = normalize_risk(alert)
        counts[risk_label] += 1
        findings.append(
            {
                "plugin_id": alert.get("pluginid"),
                "name": alert.get("alert"),
                "risk": risk_label,
                "risk_code": risk_code,
                "instances": len(alert.get("instances", [])),
            }
        )

    failing = [finding for finding in findings if finding["risk_code"] >= fail_threshold]
    summary = {
        "status": "passed" if not failing else "failed",
        "fail_on_risk": args.fail_on_risk,
        "counts": counts,
        "failing_findings": failing,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
