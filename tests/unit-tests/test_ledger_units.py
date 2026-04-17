import asyncio
import datetime

from conftest import load_service_module


ledger_db = load_service_module("ledger-service", "app.db")


class SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeLedgerSession:
    def __init__(self, scalar_results=None):
        self.scalar_results = list(scalar_results or [])
        self.added = []
        self.commits = 0
        self.refreshed = []

    async def scalar(self, _query):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


def test_upsert_contact_creates_new_contact():
    session = FakeLedgerSession([None])
    txn = {
        "payment_type": "p2p",
        "user_id": "user-1",
        "p2p_contact": {
            "contact_id": "contact-1",
            "display_name": "Alex",
            "email": "alex@example.com",
        },
    }

    contact_id = asyncio.run(ledger_db.upsert_contact(session, txn))

    assert contact_id == "contact-1"
    assert len(session.added) == 1
    assert session.added[0].display_name == "Alex"


def test_upsert_contact_updates_existing_contact():
    existing = ledger_db.P2PContact(
        user_id="user-1",
        contact_id="contact-1",
        display_name="Old Name",
        email="old@example.com",
        deleted_at=datetime.datetime.utcnow(),
    )
    session = FakeLedgerSession([existing])
    txn = {
        "payment_type": "p2p",
        "user_id": "user-1",
        "p2p_contact": {
            "contact_id": "contact-1",
            "display_name": "New Name",
            "email": "new@example.com",
        },
    }

    contact_id = asyncio.run(ledger_db.upsert_contact(session, txn))

    assert contact_id == "contact-1"
    assert existing.display_name == "New Name"
    assert existing.email == "new@example.com"
    assert existing.deleted_at is None


def test_record_transaction_returns_existing_duplicate(monkeypatch):
    existing = ledger_db.Transaction(txn_id="txn-dup")
    session = FakeLedgerSession([existing])
    monkeypatch.setattr(ledger_db, "AsyncSessionLocal", lambda: SessionContext(session))

    recorded, created = asyncio.run(
        ledger_db.record_transaction({"txn_id": "txn-dup", "user_id": "user-1", "amount": 10.0})
    )

    assert recorded is existing
    assert created is False
    assert session.commits == 0


def test_record_transaction_stores_new_record(monkeypatch):
    session = FakeLedgerSession([None])

    async def fake_upsert_contact(_session, _txn):
        return "contact-55"

    monkeypatch.setattr(ledger_db, "AsyncSessionLocal", lambda: SessionContext(session))
    monkeypatch.setattr(ledger_db, "upsert_contact", fake_upsert_contact)

    txn = {
        "txn_id": "txn-new",
        "user_id": "user-1",
        "merchant_id": "merchant-demo",
        "amount": 42.0,
        "payment_type": "p2p",
        "status": "approved",
        "final_status": "approved",
        "high_value": True,
        "payment_token": "tok_123",
        "masked_pan": "**** **** **** 1111",
        "pan_fingerprint": "abc123",
    }

    recorded, created = asyncio.run(ledger_db.record_transaction(txn))

    assert created is True
    assert recorded.txn_id == "txn-new"
    assert recorded.p2p_contact_id == "contact-55"
    assert recorded.high_value == "true"
    assert session.commits == 1
    assert session.added[0] is recorded


def test_delete_contact_scrubs_pii(monkeypatch):
    contact = ledger_db.P2PContact(
        user_id="user-1",
        contact_id="contact-1",
        display_name="Alex",
        email="alex@example.com",
    )
    session = FakeLedgerSession([contact])
    monkeypatch.setattr(ledger_db, "AsyncSessionLocal", lambda: SessionContext(session))

    deleted = asyncio.run(ledger_db.delete_contact("user-1", "contact-1"))

    assert deleted["deleted"] is True
    assert deleted["display_name"] is None
    assert deleted["email"] is None
    assert session.commits == 1
