import os
import pathlib
import subprocess
import time

import pytest
import requests


testcontainers = pytest.importorskip("testcontainers.compose")
DockerCompose = testcontainers.DockerCompose

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPOSE_DIR = REPO_ROOT / "infra" / "docker"
COMPOSE_FILE_NAME = "docker-compose.integration.yml"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY") or "issuer-admin-key"


def docker_accessible() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["docker", "info"],
            cwd=str(COMPOSE_DIR),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except OSError as exc:
        return False, str(exc)

    if completed.returncode == 0:
        return True, ""

    return False, (completed.stderr or completed.stdout or "docker unavailable").strip()


def wait_for_http(url: str, timeout_seconds: int = 120):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise AssertionError(f"Timed out waiting for {url}")


def wait_for_ledger(base_url: str, txn_id: str, timeout_seconds: int = 40) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{base_url}/v1/ledger/{txn_id}", timeout=5)
        if response.status_code == 200:
            payload = response.json()
            if payload.get("final_status") in {"approved", "declined"}:
                return payload
        time.sleep(2)
    raise AssertionError(f"Timed out waiting for testcontainers ledger state for {txn_id}")


@pytest.mark.integration
def test_transaction_flow_with_testcontainers():
    accessible, reason = docker_accessible()
    if not accessible:
        pytest.skip(f"Docker access unavailable for Testcontainers: {reason}")

    with DockerCompose(str(COMPOSE_DIR), compose_file_name=COMPOSE_FILE_NAME) as compose:
        gateway_port = compose.get_service_port("api-gateway", 8000)
        auth_port = compose.get_service_port("auth-service", 8100)
        ledger_port = compose.get_service_port("ledger-service", 8200)

        gateway_url = f"http://localhost:{gateway_port}"
        auth_url = f"http://localhost:{auth_port}"
        ledger_url = f"http://localhost:{ledger_port}"

        wait_for_http(f"{auth_url}/health")
        wait_for_http(f"{gateway_url}/health")
        wait_for_http(f"{ledger_url}/health")

        token_response = requests.post(
            f"{auth_url}/v1/token",
            json={"subject": "testcontainers-integration", "expires_in_seconds": 3600},
            headers={"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
            timeout=10,
        )
        assert token_response.status_code == 200
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}

        txn_id = "testcontainers-txn-001"
        payment_response = requests.post(
            f"{gateway_url}/v1/payments",
            headers=headers,
            json={
                "txn_id": txn_id,
                "user_id": "testcontainers-user",
                "idempotency_key": "idem-testcontainers-txn-001",
                "amount": 64.25,
                "currency": "USD",
                "payment_type": "credit",
                "merchant_id": "merchant-demo",
                "lat_lon": [41.8781, -87.6298],
                "ip_address": "198.51.100.55",
            },
            timeout=10,
        )
        assert payment_response.status_code == 200
        assert payment_response.json()["status"] == "accepted"

        ledger_record = wait_for_ledger(ledger_url, txn_id)
        assert ledger_record["txn_id"] == txn_id
        assert ledger_record["processor_status"] == "approved"
        assert ledger_record["final_status"] == "approved"
