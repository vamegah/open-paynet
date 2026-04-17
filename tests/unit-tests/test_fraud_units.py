import asyncio

from conftest import load_service_module


fraud = load_service_module("fraud-service", "app.rules_engine")


def test_evaluate_fraud_skips_already_declined_transaction():
    txn = {"txn_id": "txn-skip", "final_status": "declined"}

    evaluated = asyncio.run(fraud.evaluate_fraud(txn))

    assert evaluated["fraud_status"] == "skipped"
    assert evaluated["processing_stage"] == "completed"
    assert evaluated["fraud_suspicious"] is False


def test_evaluate_fraud_flags_velocity(monkeypatch):
    async def always_true(*_args, **_kwargs):
        return True

    async def always_false(*_args, **_kwargs):
        return False

    monkeypatch.setattr(fraud, "velocity_check", always_true)
    monkeypatch.setattr(fraud, "geo_mismatch_check", always_false)
    monkeypatch.setattr(fraud, "ip_reputation_check", always_false)

    txn = {"txn_id": "txn-velocity", "user_id": "user-1", "amount": 50.0}

    evaluated = asyncio.run(fraud.evaluate_fraud(txn))

    assert evaluated["final_status"] == "declined"
    assert evaluated["fraud_status"] == "flagged"
    assert "Velocity exceeded" in evaluated["decision_reason"]


def test_evaluate_fraud_approves_clean_transaction(monkeypatch):
    async def always_false(*_args, **_kwargs):
        return False

    monkeypatch.setattr(fraud, "velocity_check", always_false)
    monkeypatch.setattr(fraud, "geo_mismatch_check", always_false)
    monkeypatch.setattr(fraud, "ip_reputation_check", always_false)

    txn = {
        "txn_id": "txn-clean",
        "user_id": "user-2",
        "amount": 80.0,
        "lat_lon": [41.8781, -87.6298],
        "ip_address": "198.51.100.10",
    }

    evaluated = asyncio.run(fraud.evaluate_fraud(txn))

    assert evaluated["final_status"] == "approved"
    assert evaluated["fraud_status"] == "cleared"
    assert evaluated["decision_reason"] == "Approved after fraud evaluation"
