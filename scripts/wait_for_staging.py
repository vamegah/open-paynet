import argparse
import json
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_TARGETS = [
    "http://localhost:18100/health",
    "http://localhost:18000/health",
    "http://localhost:18200/health",
    "http://localhost:18300/health",
    "http://localhost:19090/-/ready",
    "http://localhost:13000/login",
]


def check_url(url: str) -> tuple[bool, int | None, str]:
    try:
        with urlopen(url, timeout=5) as response:
            return True, response.status, ""
    except HTTPError as exc:
        return False, exc.code, exc.reason
    except URLError as exc:
        return False, None, str(exc.reason)


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for local staging endpoints to become reachable.")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--targets", nargs="*", default=DEFAULT_TARGETS)
    args = parser.parse_args()

    deadline = time.time() + args.timeout_seconds
    last_status = []

    while time.time() < deadline:
        last_status = []
        all_ready = True
        for url in args.targets:
            ok, status, error = check_url(url)
            last_status.append({"url": url, "ok": ok, "status": status, "error": error})
            if not ok:
                all_ready = False
        if all_ready:
            print(json.dumps({"status": "ok", "targets": last_status}, sort_keys=True))
            return 0
        time.sleep(3)

    print(json.dumps({"status": "failed", "targets": last_status}, sort_keys=True))
    return 1


if __name__ == "__main__":
    sys.exit(main())
