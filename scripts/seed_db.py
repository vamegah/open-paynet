import json
import os
import sys
import time
import uuid
from urllib.request import Request, urlopen


AUTH_URL = "http://localhost:18100/v1/token"
PAYMENT_URL = "http://localhost:18000/v1/payments"
TOKEN_ISSUER_ADMIN_KEY = os.getenv("TOKEN_ISSUER_ADMIN_KEY", "issuer-admin-key")


def post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    txn_id = f"restore-smoke-{uuid.uuid4()}"
    token_response = post_json(
        AUTH_URL,
        {"subject": "restore-smoke-user"},
        {"X-Token-Issuer-Key": TOKEN_ISSUER_ADMIN_KEY},
    )
    payment_response = post_json(
        PAYMENT_URL,
        {
            "txn_id": txn_id,
            "user_id": "restore-smoke-user",
            "merchant_id": "merchant-demo",
            "amount": 42.5,
            "currency": "USD",
            "payment_type": "credit",
            "idempotency_key": f"idem-{txn_id}",
            "lat_lon": [41.8781, -87.6298],
            "ip_address": "198.51.100.10",
        },
        {"Authorization": f"Bearer {token_response['access_token']}"},
    )
    print(
        json.dumps(
            {
                "status": "queued",
                "txn_id": txn_id,
                "payment_response": payment_response,
                "created_at_epoch": time.time(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
