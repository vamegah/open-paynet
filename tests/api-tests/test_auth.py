import asyncio
import importlib.util
import os
import sys
from pathlib import Path

from fastapi import HTTPException
from jose import jwt
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
AUTH_SERVICE_ROOT = REPO_ROOT / "services" / "auth-service"
FRAUD_SERVICE_ROOT = REPO_ROOT / "services" / "fraud-service"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def configure_auth_env():
    os.environ["ALLOW_INSECURE_DEFAULT_SECRETS"] = "true"
    os.environ["JWT_SECRET"] = "supersecret"
    os.environ["TOKEN_ISSUER_ADMIN_KEY"] = "issuer-admin-key"
    os.environ["JWT_ISSUER"] = "openpaynet-auth"
    os.environ["JWT_AUDIENCE"] = "openpaynet-api"
    os.environ["DEFAULT_SUBJECT_ROLE"] = "payment_initiator"
    os.environ["DEFAULT_SUBJECT_SCOPES"] = "payments:write ledger:read"
    os.environ["SUBJECT_POLICIES_JSON"] = (
        '{"*":{"role":"payment_initiator","scopes":["payments:write","ledger:read"],"allowed_roles":["payment_initiator"]}}'
    )
    os.environ["MERCHANT_CREDENTIALS_JSON"] = (
        '{"merchant-demo":{"api_key":"demo-key","role":"merchant","scopes":["payments:write","ledger:read"]}}'
    )


def test_auth_service_validates_api_key():
    configure_auth_env()
    auth_module = load_module("openpaynet_auth_service_main", AUTH_SERVICE_ROOT / "app" / "main.py")
    result = asyncio.run(auth_module.validate_api_key(auth_module.ApiKeyValidationRequest(api_key="demo-key")))
    assert result["merchant_id"] == "merchant-demo"
    assert result["status"] == "valid"
    assert result["role"] == "merchant"
    assert "payments:write" in result["scopes"]


def test_auth_service_issues_scoped_token():
    configure_auth_env()
    auth_module = load_module("openpaynet_auth_service_main_scoped", AUTH_SERVICE_ROOT / "app" / "main.py")
    result = asyncio.run(
        auth_module.issue_token(
            auth_module.TokenRequest(
                subject="auth-scope-tester",
                requested_scopes=["payments:write"],
            ),
            x_token_issuer_key="issuer-admin-key",
        )
    )
    payload = jwt.decode(
        result["access_token"],
        auth_module.settings.JWT_SECRET,
        algorithms=["HS256"],
        issuer=auth_module.settings.JWT_ISSUER,
        audience=auth_module.settings.JWT_AUDIENCE,
    )
    assert payload["role"] == "payment_initiator"
    assert payload["scopes"] == ["payments:write"]


def test_auth_service_requires_token_issuer_key():
    configure_auth_env()
    auth_module = load_module("openpaynet_auth_service_main_protected", AUTH_SERVICE_ROOT / "app" / "main.py")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            auth_module.issue_token(
                auth_module.TokenRequest(subject="missing-admin-key"),
                x_token_issuer_key=None,
            )
        )

    assert exc_info.value.status_code == 401


def test_fraud_rules_flag_bad_ip_and_geo_mismatch(monkeypatch):
    sys.path.insert(0, str(FRAUD_SERVICE_ROOT))
    rules_module = load_module("openpaynet_fraud_rules", FRAUD_SERVICE_ROOT / "app" / "rules_engine.py")

    class FakeRedis:
        def __init__(self):
            self.store = {
                "user_last_location:user-geo": "41.8781,-87.6298",
            }

        async def get(self, key):
            return self.store.get(key)

        async def incr(self, key):
            current = int(self.store.get(key, 0)) + 1
            self.store[key] = str(current)
            return current

        async def expire(self, key, period):
            return True

        async def set(self, key, value, ex=None):
            self.store[key] = value
            return True

    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(rules_module, "get_redis", fake_get_redis)
    monkeypatch.setattr(rules_module, "BAD_IP_ADDRESSES", {"203.0.113.66"})

    flagged_geo = asyncio.run(
        rules_module.evaluate_fraud(
            {
                "txn_id": "txn-fraud-geo",
                "user_id": "user-geo",
                "amount": 250,
                "payment_type": "credit",
                "final_status": "pending_fraud_review",
                "lat_lon": [34.0522, -118.2437],
                "ip_address": "198.51.100.12",
            }
        )
    )
    assert flagged_geo["final_status"] == "declined"
    assert flagged_geo["fraud_status"] == "flagged"
    assert flagged_geo["decision_reason"] == "Geo mismatch detected"

    flagged_ip = asyncio.run(
        rules_module.evaluate_fraud(
            {
                "txn_id": "txn-fraud-ip",
                "user_id": "user-ip",
                "amount": 100,
                "payment_type": "credit",
                "final_status": "pending_fraud_review",
                "lat_lon": [41.8781, -87.6298],
                "ip_address": "203.0.113.66",
            }
        )
    )
    assert flagged_ip["final_status"] == "declined"
    assert flagged_ip["fraud_status"] == "flagged"
    assert flagged_ip["decision_reason"] == "High-risk IP reputation"
