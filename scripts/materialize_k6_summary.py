import argparse
import json
from pathlib import Path


def extract_summary(raw_text: str) -> dict:
    candidate_texts = [raw_text.strip()]

    first_brace = raw_text.find("{")
    last_brace = raw_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate_texts.append(raw_text[first_brace : last_brace + 1].strip())

    for candidate in candidate_texts:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "metrics" in parsed:
            return parsed

    raise ValueError("Unable to extract a valid k6 summary from the provided stdout log.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a k6 summary artifact from stdout when direct file export is unavailable.")
    parser.add_argument("--summary", required=True, help="Expected summary JSON path.")
    parser.add_argument("--stdout-log", required=True, help="Captured k6 stdout log path.")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if summary_path.exists():
        print(f"k6 summary already present at {summary_path}")
        return 0

    stdout_path = Path(args.stdout_log)
    if not stdout_path.exists():
        raise FileNotFoundError(f"k6 stdout log not found: {stdout_path}")

    summary = extract_summary(stdout_path.read_text(encoding="utf-8"))
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Materialized k6 summary at {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
