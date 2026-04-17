import json
import os
import pathlib
import time

import requests


BASE_DIR = pathlib.Path(__file__).resolve().parent
CONTRACT_PATH = BASE_DIR / "contracts" / "payment-ledger-contract.json"
API_GATEWAY_URL = "http://localhost:18000"
LEDGER_URL = "http://localhost:18200"
AUTH_URL = "http://localhost:18100"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY") or "issuer-admin-key"


def load_contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def issue_token(subject: str = "contract-tester") -> dict[str, str]:
    response = requests.post(
        f"{AUTH_URL}/v1/token",
        json={"subject": subject, "expires_in_seconds": 3600},
        headers={"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
        timeout=10,
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def wait_for_ledger(txn_id: str, timeout_seconds: int = 20) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{LEDGER_URL}/v1/ledger/{txn_id}", timeout=10)
        if response.status_code == 200:
            payload = response.json()
            if payload.get("final_status") in {"approved", "declined"}:
                return payload
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for ledger contract record for {txn_id}")


def matches_declared_type(expected_type: str, value) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise AssertionError(f"Unsupported contract type: {expected_type}")


def test_payment_to_ledger_contract():
    contract = load_contract()
    interaction = contract["interactions"][0]
    headers = issue_token("payment-ledger-contract")
    txn_id = "contract-ledger-001"

    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": txn_id,
            "user_id": "contract-user-001",
            "idempotency_key": "idem-contract-ledger-001",
            "amount": 88.75,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.31",
        },
        timeout=10,
    )
    assert response.status_code == 200

    ledger_payload = wait_for_ledger(txn_id)
    expected_response = interaction["response"]

    for field_name, field_type in expected_response["requiredFields"].items():
        assert field_name in ledger_payload, f"Missing contract field: {field_name}"
        assert matches_declared_type(field_type, ledger_payload[field_name]), (
            f"Field {field_name} did not match contract type {field_type}: "
            f"{ledger_payload[field_name]!r}"
        )

    assert ledger_payload["txn_id"] == txn_id
    assert ledger_payload["payment_type"] in expected_response["allowedPaymentTypes"]
    assert ledger_payload["final_status"] in expected_response["allowedFinalStatuses"]
