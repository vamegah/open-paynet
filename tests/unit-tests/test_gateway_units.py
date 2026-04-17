import asyncio

import pytest
from fastapi import HTTPException

from conftest import load_service_module


idempotency = load_service_module("api-gateway", "app.core.idempotency")
tokenization = load_service_module("api-gateway", "app.core.tokenization")


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True


def test_idempotency_cache_round_trip(monkeypatch):
    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(idempotency, "get_redis", fake_get_redis)
    payload = {"status": "accepted", "txn_id": "txn-idem"}

    asyncio.run(idempotency.cache_response("idem-1", payload, ttl_seconds=120))
    cached = asyncio.run(idempotency.get_cached_response("idem-1"))

    assert cached == payload


def test_idempotency_returns_none_when_missing(monkeypatch):
    fake_redis = FakeRedis()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(idempotency, "get_redis", fake_get_redis)

    cached = asyncio.run(idempotency.get_cached_response("missing-key"))

    assert cached is None


def test_tokenize_pan_masks_and_hashes():
    tokenized = tokenization.tokenize_pan("4111 1111 1111 1111")

    assert tokenized["payment_token"].startswith("tok_")
    assert tokenized["masked_pan"] == "**** **** **** 1111"
    assert len(tokenized["pan_fingerprint"]) == 64


def test_tokenize_pan_rejects_invalid_input():
    with pytest.raises(HTTPException) as exc_info:
        tokenization.tokenize_pan("not-a-pan")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid PAN format"
