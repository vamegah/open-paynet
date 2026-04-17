import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE_FILE = REPO_ROOT / "infra" / "docker" / "docker-compose.yml"
API_GATEWAY_URL = "http://localhost:18000"
AUTH_URL = "http://localhost:18100"
LEDGER_URL = "http://localhost:18200"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY") or "issuer-admin-key"


class ChaosFailure(RuntimeError):
    pass


def http_json(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 10,
) -> tuple[int, dict, dict[str, str]]:
    body = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(raw), dict(response.headers.items())
    except TimeoutError:
        return 504, {"detail": "request timed out"}, {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8") or "{}"
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"detail": raw}
        return exc.code, parsed, dict(exc.headers.items())
    except URLError as exc:
        raise ChaosFailure(f"HTTP request failed for {url}: {exc.reason}") from exc


def docker_compose(compose_file: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-f", str(compose_file), *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def wait_for_url(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            status, _, _ = http_json("GET", url, headers={"Accept": "application/json"}, timeout=5)
            if status == 200:
                return
        except ChaosFailure:
            pass
        time.sleep(2)
    raise ChaosFailure(f"Timed out waiting for {url}")


def wait_for_kafka_ready(compose_file: Path, timeout_seconds: int = 150) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "kafka",
                "bash",
                "-lc",
                "kafka-topics --bootstrap-server kafka:9092 --list",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and "payment-initiated" in result.stdout:
            return
        time.sleep(5)
    raise ChaosFailure("Timed out waiting for Kafka to accept topic operations")


def wait_for_ledger_state(txn_id: str, expected_states: set[str], timeout_seconds: int = 45) -> dict:
    deadline = time.time() + timeout_seconds
    last_payload: dict | None = None
    while time.time() < deadline:
        status, payload, _ = http_json("GET", f"{LEDGER_URL}/v1/ledger/{txn_id}", timeout=5)
        if status == 200:
            last_payload = payload
            if payload.get("final_status") in expected_states:
                return payload
        time.sleep(2)
    raise ChaosFailure(f"Timed out waiting for ledger state for {txn_id}: {last_payload}")


def assert_ledger_missing(txn_id: str, duration_seconds: int = 8) -> None:
    deadline = time.time() + duration_seconds
    while time.time() < deadline:
        status, _, _ = http_json("GET", f"{LEDGER_URL}/v1/ledger/{txn_id}", timeout=5)
        if status != 404:
            raise ChaosFailure(f"Expected no ledger record for {txn_id} during outage, got {status}")
        time.sleep(2)


def issue_token(subject: str) -> str:
    status, payload, _ = http_json(
        "POST",
        f"{AUTH_URL}/v1/token",
        payload={"subject": subject, "expires_in_seconds": 3600},
        headers={"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
        timeout=10,
    )
    if status != 200:
        raise ChaosFailure(f"Failed to issue auth token: {status} {payload}")
    return payload["access_token"]


def submit_payment(txn_id: str, subject: str, amount: float = 125.0) -> tuple[int, dict]:
    token = issue_token(subject)
    status, payload, _ = http_json(
        "POST",
        f"{API_GATEWAY_URL}/v1/payments",
        payload={
            "txn_id": txn_id,
            "user_id": subject,
            "idempotency_key": f"idem-{txn_id}",
            "amount": amount,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.90",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    return status, payload


def wait_for_successful_payment(timeout_seconds: int = 45) -> tuple[str, dict]:
    deadline = time.time() + timeout_seconds
    last_response: tuple[int, dict] | None = None
    while time.time() < deadline:
        txn_id = f"chaos-recovery-{uuid.uuid4().hex[:12]}"
        status, payload = submit_payment(txn_id, f"chaos-recovery-{uuid.uuid4().hex[:8]}")
        last_response = (status, payload)
        if status == 200 and payload.get("processing_stage") == "queued":
            return txn_id, payload
        time.sleep(3)
    raise ChaosFailure(f"Expected successful recovery payment after dependency restart, got {last_response}")


def warm_system(timeout_seconds: int = 60) -> None:
    txn_id, _ = wait_for_successful_payment(timeout_seconds=timeout_seconds)
    wait_for_ledger_state(txn_id, {"approved", "declined"}, timeout_seconds=timeout_seconds)


def run_payment_service_stop_drill(compose_file: Path) -> dict:
    txn_id = f"chaos-payment-{uuid.uuid4().hex[:12]}"
    summary = {"drill": "payment-service-stop", "txn_id": txn_id}
    docker_compose(compose_file, "stop", "payment-service")
    try:
        status, payload = submit_payment(txn_id, f"chaos-payer-{uuid.uuid4().hex[:8]}")
        if status != 200 or payload.get("processing_stage") != "queued":
            raise ChaosFailure(f"Expected queued payment while processor is down, got {status} {payload}")
        assert_ledger_missing(txn_id, duration_seconds=6)
    finally:
        docker_compose(compose_file, "start", "payment-service")

    ledger_record = wait_for_ledger_state(txn_id, {"approved", "declined"}, timeout_seconds=60)
    summary["gateway_status"] = status
    summary["final_status"] = ledger_record.get("final_status")
    summary["processing_stage"] = ledger_record.get("processing_stage")
    summary["trace_id"] = ledger_record.get("trace_id")
    return summary


def run_kafka_outage_drill(compose_file: Path) -> dict:
    failed_statuses: list[int] = []
    outage_txn_ids: list[str] = []
    summary = {"drill": "kafka-outage"}
    docker_compose(compose_file, "stop", "kafka")
    time.sleep(5)
    try:
        for index in range(4):
            txn_id = f"chaos-kafka-{index}-{uuid.uuid4().hex[:10]}"
            outage_txn_ids.append(txn_id)
            status, _ = submit_payment(txn_id, f"chaos-outage-{index}-{uuid.uuid4().hex[:6]}")
            failed_statuses.append(status)
        if not all(status in {503, 504} for status in failed_statuses):
            raise ChaosFailure(f"Expected degraded 503/504 responses during Kafka outage, got {failed_statuses}")
    finally:
        docker_compose(compose_file, "start", "kafka")

    wait_for_kafka_ready(compose_file, timeout_seconds=150)
    docker_compose(compose_file, "up", "-d", "kafka-init")
    wait_for_url("http://localhost:18000/health", timeout_seconds=60)
    time.sleep(10)
    recovery_txn_id, _ = wait_for_successful_payment(timeout_seconds=120)

    ledger_record = wait_for_ledger_state(recovery_txn_id, {"approved", "declined"}, timeout_seconds=60)

    for txn_id in outage_txn_ids:
        status, _, _ = http_json("GET", f"{LEDGER_URL}/v1/ledger/{txn_id}", timeout=5)
        if status != 404:
            raise ChaosFailure(f"Outage payment {txn_id} should not have been recorded in ledger, got {status}")

    summary["outage_statuses"] = failed_statuses
    summary["recovery_txn_id"] = recovery_txn_id
    summary["recovery_final_status"] = ledger_record.get("final_status")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenPayNet chaos drills against the live Docker stack.")
    parser.add_argument(
        "--drill",
        choices=["payment-service-stop", "kafka-outage", "all"],
        default="all",
    )
    parser.add_argument(
        "--compose-file",
        default=str(DEFAULT_COMPOSE_FILE),
        help="Path to the docker-compose.yml used by the local stack.",
    )
    args = parser.parse_args()

    compose_file = Path(args.compose_file).resolve()
    wait_for_url(f"{AUTH_URL}/health", timeout_seconds=30)
    wait_for_url(f"{API_GATEWAY_URL}/health", timeout_seconds=30)
    wait_for_url(f"{LEDGER_URL}/health", timeout_seconds=30)
    warm_system(timeout_seconds=75)

    results = []
    try:
        if args.drill in {"payment-service-stop", "all"}:
            results.append(run_payment_service_stop_drill(compose_file))
            warm_system(timeout_seconds=75)
        if args.drill in {"kafka-outage", "all"}:
            results.append(run_kafka_outage_drill(compose_file))
    except subprocess.CalledProcessError as exc:
        raise ChaosFailure(exc.stderr.strip() or exc.stdout.strip() or str(exc)) from exc

    print(json.dumps({"status": "passed", "results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ChaosFailure as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2, sort_keys=True))
        sys.exit(1)
