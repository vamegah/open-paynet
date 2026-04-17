import os
import pytest
import requests
import time

API_GATEWAY_URL = "http://localhost:18000"
LEDGER_URL = "http://localhost:18200"
AUTH_URL = "http://localhost:18100"
NOTIFICATION_URL = "http://localhost:18300"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY") or "issuer-admin-key"


def wait_for_ledger_state(txn_id: str, timeout_seconds: int = 20):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{LEDGER_URL}/v1/ledger/{txn_id}")
        if response.status_code == 200:
            payload = response.json()
            if payload.get("final_status") in {"approved", "declined"}:
                return payload
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for ledger state for {txn_id}")


def wait_for_notification(txn_id: str, timeout_seconds: int = 20):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{NOTIFICATION_URL}/v1/notifications/{txn_id}", timeout=10)
        if response.status_code == 200:
            return response.json()
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for notification for {txn_id}")


def post_payment_with_retry(payment_data: dict, headers: dict, timeout_seconds: int = 20):
    deadline = time.time() + timeout_seconds
    last_response = None
    while time.time() < deadline:
        response = requests.post(f"{API_GATEWAY_URL}/v1/payments", json=payment_data, headers=headers, timeout=10)
        if response.status_code == 200:
            return response
        if response.status_code not in {503, 504}:
            return response
        last_response = response
        time.sleep(1)
    return last_response


@pytest.fixture(scope="module")
def auth_headers():
    response = requests.post(
        f"{AUTH_URL}/v1/token",
        json={"subject": "integration-tester", "expires_in_seconds": 3600},
        headers={"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
        timeout=10,
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="module")
def wait_for_kafka():
    time.sleep(8)
    yield

def test_full_transaction_flow(wait_for_kafka, auth_headers):
    payment_data = {
        "txn_id": "test-txn-001",
        "user_id": "user123",
        "idempotency_key": "idem-test-txn-001",
        "amount": 250.00,
        "currency": "USD",
        "payment_type": "credit",
        "merchant_id": "merchant-demo",
        "lat_lon": [40.7128, -74.0060],
        "ip_address": "192.168.1.1"
    }
    resp = post_payment_with_retry(payment_data, auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"
    assert resp.json()["processing_stage"] == "queued"
    txn_id = resp.json()["txn_id"]

    ledger_record = wait_for_ledger_state(txn_id)
    assert ledger_record["status"] == "approved"
    assert ledger_record["final_status"] == "approved"
    assert ledger_record["processor_status"] == "approved"
    assert ledger_record["fraud_status"] == "cleared"
    assert ledger_record["payment_type"] == "credit"
    assert ledger_record["idempotency_key"] == "idem-test-txn-001"


def test_fraud_trigger_declines_transaction(auth_headers):
    payment_data = {
        "txn_id": "test-txn-fraud",
        "user_id": "user123",
        "idempotency_key": "idem-test-txn-fraud",
        "amount": 1500.00,
        "currency": "USD",
        "payment_type": "credit",
        "merchant_id": "merchant-demo",
        "lat_lon": None,
        "ip_address": "192.168.1.1"
    }
    resp = post_payment_with_retry(payment_data, auth_headers)
    assert resp.status_code == 200
    txn_id = resp.json()["txn_id"]

    ledger_record = wait_for_ledger_state(txn_id)
    assert ledger_record["status"] == "declined"
    assert ledger_record["final_status"] == "declined"
    assert ledger_record["fraud_status"] == "flagged"
    assert "location" in ledger_record["decision_reason"].lower()

    notification = wait_for_notification(txn_id)
    assert notification["template"] == "payment-declined"
    assert notification["channels"] == ["email", "slack"]
    assert notification["severity"] == "critical"


def test_processor_decline_for_p2p_limit(auth_headers):
    payment_data = {
        "txn_id": "test-txn-p2p-limit",
        "user_id": "user789",
        "idempotency_key": "idem-test-txn-p2p-limit",
        "amount": 2500.00,
        "currency": "USD",
        "payment_type": "p2p",
        "merchant_id": "merchant-demo",
        "lat_lon": [41.8781, -87.6298],
        "ip_address": "198.51.100.44",
    }
    resp = post_payment_with_retry(payment_data, auth_headers)
    assert resp.status_code == 200

    ledger_record = wait_for_ledger_state(payment_data["txn_id"])
    assert ledger_record["status"] == "declined"
    assert ledger_record["final_status"] == "declined"
    assert ledger_record["processor_status"] == "rejected"
    assert ledger_record["fraud_status"] == "skipped"
    assert ledger_record["decision_reason"] == "P2P amount exceeds limit"

    notification = wait_for_notification(payment_data["txn_id"])
    assert notification["template"] == "payment-declined"
    assert notification["channels"] == ["email", "slack"]
    assert notification["severity"] == "critical"


def test_high_value_approved_payment_triggers_slack_notification(auth_headers):
    payment_data = {
        "txn_id": "test-txn-high-value-approved",
        "user_id": "user-high-value",
        "idempotency_key": "idem-test-txn-high-value-approved",
        "amount": 1200.00,
        "currency": "USD",
        "payment_type": "credit",
        "merchant_id": "merchant-demo",
        "lat_lon": [41.8781, -87.6298],
        "ip_address": "198.51.100.88",
    }
    resp = post_payment_with_retry(payment_data, auth_headers)
    assert resp.status_code == 200

    ledger_record = wait_for_ledger_state(payment_data["txn_id"])
    assert ledger_record["final_status"] == "approved"
    assert ledger_record["high_value"] == "true"

    notification = wait_for_notification(payment_data["txn_id"])
    assert notification["template"] == "high-value-payment"
    assert notification["channels"] == ["slack"]
    assert notification["severity"] == "medium"
