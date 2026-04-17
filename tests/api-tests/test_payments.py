import os
import requests
import time
import uuid


API_GATEWAY_URL = "http://localhost:18000"
AUTH_URL = "http://localhost:18100"
LEDGER_URL = "http://localhost:18200"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY") or "issuer-admin-key"


def issue_token(subject: str = "api-test-user", requested_scopes: list[str] | None = None) -> dict[str, str]:
    response = requests.post(
        f"{AUTH_URL}/v1/token",
        json={
            "subject": subject,
            "expires_in_seconds": 3600,
            "requested_scopes": requested_scopes or ["payments:write", "ledger:read"],
        },
        headers={"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
        timeout=10,
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def wait_for_ledger_state(txn_id: str, timeout_seconds: int = 20) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{LEDGER_URL}/v1/ledger/{txn_id}", timeout=10)
        if response.status_code == 200:
            payload = response.json()
            if payload.get("final_status") in {"approved", "declined"}:
                return payload
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for ledger state for {txn_id}")


def test_payment_accepts_and_returns_contract():
    headers = issue_token("api-contract-tester")
    headers["x-trace-id"] = "trace-api-001"

    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": "txn-api-001",
            "user_id": "user-123",
            "idempotency_key": "idem-api-001",
            "amount": 99.5,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.20",
        },
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["processing_stage"] == "queued"
    assert payload["txn_id"] == "txn-api-001"
    assert payload["trace_id"] == "trace-api-001"
    assert payload["payment_type"] == "credit"
    assert payload["merchant_id"] == "merchant-demo"
    assert payload["authenticated_subject"] == "api-contract-tester"


def test_credit_payment_tokenizes_pan_without_storing_raw_pan():
    headers = issue_token("api-tokenization-tester")
    txn_id = "txn-api-tokenized-001"
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": txn_id,
            "user_id": "user-tokenized-001",
            "idempotency_key": "idem-api-tokenized-001",
            "amount": 82.0,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "card_pan": "4111111111111111",
        },
        timeout=10,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tokenized"] is True
    assert payload["payment_token"].startswith("tok_")

    ledger_record = wait_for_ledger_state(txn_id)
    assert ledger_record["payment_token"].startswith("tok_")
    assert ledger_record["masked_pan"] == "**** **** **** 1111"
    assert "card_pan" not in ledger_record


def test_payment_replays_cached_idempotent_response():
    headers = issue_token("api-idempotency-tester")

    payload = {
        "txn_id": "txn-api-002",
        "user_id": "user-456",
        "idempotency_key": "idem-api-002",
        "amount": 120.0,
        "currency": "USD",
        "payment_type": "p2p",
        "merchant_id": "merchant-demo",
        "lat_lon": [41.8781, -87.6298],
        "ip_address": "198.51.100.21",
    }

    first_response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json=payload,
        timeout=10,
    )
    second_response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json=payload,
        timeout=10,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()


def test_payment_requires_authentication():
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        json={
            "txn_id": "txn-api-unauth",
            "user_id": "user-unauth",
            "idempotency_key": "idem-api-unauth",
            "amount": 25.0,
            "currency": "USD",
            "payment_type": "credit",
        },
        timeout=10,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_payment_rejects_missing_payment_scope():
    headers = issue_token("api-no-payment-scope", requested_scopes=["ledger:read"])
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": "txn-api-no-scope",
            "user_id": "user-no-scope",
            "idempotency_key": "idem-api-no-scope",
            "amount": 30.0,
            "currency": "USD",
            "payment_type": "credit",
        },
        timeout=10,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient scope"


def test_payment_rejects_invalid_amount():
    headers = issue_token("api-invalid-amount")
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": "txn-api-invalid-amount",
            "user_id": "user-invalid-amount",
            "idempotency_key": "idem-api-invalid-amount",
            "amount": -10.0,
            "currency": "USD",
            "payment_type": "credit",
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Amount must be positive"


def test_payment_accepts_merchant_api_key_auth():
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers={"x-api-key": "demo-key"},
        json={
            "txn_id": "txn-api-merchant-key",
            "user_id": "merchant-user-001",
            "idempotency_key": "idem-api-merchant-key",
            "amount": 60.0,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.46",
        },
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["authenticated_subject"] == "merchant-demo"


def test_p2p_contact_can_be_deleted_for_gdpr():
    headers = issue_token("api-gdpr-contact")
    run_id = uuid.uuid4().hex[:8]
    txn_id = f"txn-api-gdpr-p2p-{run_id}"
    contact_id = f"contact-{run_id}"
    user_id = f"user-gdpr-{run_id}"
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": txn_id,
            "user_id": user_id,
            "idempotency_key": f"idem-api-gdpr-p2p-{run_id}",
            "amount": 40.0,
            "currency": "USD",
            "payment_type": "p2p",
            "merchant_id": "merchant-demo",
            "p2p_contact": {
                "contact_id": contact_id,
                "display_name": "Alex Friend",
                "email": "alex.friend@example.com",
            },
        },
        timeout=10,
    )
    assert response.status_code == 200

    ledger_record = wait_for_ledger_state(txn_id)
    assert ledger_record["p2p_contact_id"] == contact_id

    contact_response = requests.get(f"{LEDGER_URL}/v1/contacts/{user_id}/{contact_id}", timeout=10)
    assert contact_response.status_code == 200
    assert contact_response.json()["display_name"] == "Alex Friend"
    assert contact_response.json()["deleted"] is False

    delete_response = requests.delete(f"{LEDGER_URL}/v1/contacts/{user_id}/{contact_id}", timeout=10)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "deleted"
    assert delete_response.json()["contact"]["deleted"] is True
    assert delete_response.json()["contact"]["display_name"] is None
    assert delete_response.json()["contact"]["email"] is None


def test_payment_rejects_mismatched_merchant_api_key():
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers={"x-api-key": "demo-key"},
        json={
            "txn_id": "txn-api-merchant-mismatch",
            "user_id": "merchant-user-002",
            "idempotency_key": "idem-api-merchant-mismatch",
            "amount": 60.0,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-other",
        },
        timeout=10,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Merchant ID does not match API key"


def test_ledger_query_returns_processed_transaction():
    headers = issue_token("api-ledger-query")
    txn_id = "txn-api-ledger-001"
    response = requests.post(
        f"{API_GATEWAY_URL}/v1/payments",
        headers=headers,
        json={
            "txn_id": txn_id,
            "user_id": "user-ledger-001",
            "idempotency_key": "idem-api-ledger-001",
            "amount": 45.0,
            "currency": "USD",
            "payment_type": "credit",
            "merchant_id": "merchant-demo",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.45",
        },
        timeout=10,
    )

    assert response.status_code == 200
    ledger_record = wait_for_ledger_state(txn_id)
    assert ledger_record["txn_id"] == txn_id
    assert ledger_record["merchant_id"] == "merchant-demo"
    assert ledger_record["payment_type"] == "credit"
    assert ledger_record["final_status"] in {"approved", "declined"}


def test_ledger_query_returns_404_for_unknown_transaction():
    response = requests.get(f"{LEDGER_URL}/v1/ledger/txn-does-not-exist", timeout=10)

    assert response.status_code == 404
    assert response.json()["detail"] == "Transaction not found"
