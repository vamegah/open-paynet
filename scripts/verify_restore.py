import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fetch_json(url: str) -> tuple[int, dict]:
    try:
        with urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, {"error": body}
    except URLError as exc:
        return 0, {"error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a restored ledger transaction is readable.")
    parser.add_argument("--txn-id", required=True)
    parser.add_argument("--ledger-base-url", default="http://localhost:18200")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    deadline = time.time() + args.timeout_seconds
    url = f"{args.ledger_base_url}/v1/ledger/{args.txn_id}"

    while time.time() < deadline:
        status, payload = fetch_json(url)
        if status == 200 and payload.get("txn_id") == args.txn_id:
            print(json.dumps({"status": "ok", "txn_id": args.txn_id, "ledger_response": payload}, sort_keys=True))
            return 0
        time.sleep(2)

    print(
        json.dumps(
            {
                "status": "failed",
                "txn_id": args.txn_id,
                "ledger_url": url,
                "detail": "Transaction was not readable before timeout elapsed.",
            },
            sort_keys=True,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
