import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from shared.config import env_flag, env_text


DATABASE_URL = env_text("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@ledger-db:5432/ledger")

engine = create_async_engine(DATABASE_URL, echo=env_flag("SQLALCHEMY_ECHO", True))
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    txn_id = Column(String, unique=True, index=True)
    user_id = Column(String)
    merchant_id = Column(String, nullable=True)
    amount = Column(Float)
    currency = Column(String, default="USD")
    payment_type = Column(String, default="credit")
    status = Column(String)
    processor_status = Column(String, nullable=True)
    final_status = Column(String, nullable=True)
    decision_reason = Column(String, nullable=True)
    processing_stage = Column(String, nullable=True)
    authenticated_subject = Column(String, nullable=True)
    high_value = Column(String, nullable=True)
    fraud_status = Column(String, default="unknown")
    fraud_reason = Column(String, nullable=True)
    trace_id = Column(String, index=True)
    idempotency_key = Column(String, index=True)
    processor_ref = Column(String, nullable=True)
    payment_token = Column(String, nullable=True, index=True)
    masked_pan = Column(String, nullable=True)
    pan_fingerprint = Column(String, nullable=True)
    p2p_contact_id = Column(String, nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "txn_id": self.txn_id,
            "user_id": self.user_id,
            "merchant_id": self.merchant_id,
            "amount": self.amount,
            "currency": self.currency,
            "payment_type": self.payment_type,
            "status": self.status,
            "processor_status": self.processor_status,
            "final_status": self.final_status,
            "decision_reason": self.decision_reason,
            "processing_stage": self.processing_stage,
            "authenticated_subject": self.authenticated_subject,
            "high_value": self.high_value,
            "fraud_status": self.fraud_status,
            "fraud_reason": self.fraud_reason,
            "trace_id": self.trace_id,
            "idempotency_key": self.idempotency_key,
            "processor_ref": self.processor_ref,
            "payment_token": self.payment_token,
            "masked_pan": self.masked_pan,
            "pan_fingerprint": self.pan_fingerprint,
            "p2p_contact_id": self.p2p_contact_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class P2PContact(Base):
    __tablename__ = "p2p_contacts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    contact_id = Column(String, index=True)
    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "contact_id": self.contact_id,
            "display_name": self.display_name,
            "email": self.email,
            "deleted": self.deleted_at is not None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS payment_token VARCHAR"))
        await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS masked_pan VARCHAR"))
        await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS pan_fingerprint VARCHAR"))
        await conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS p2p_contact_id VARCHAR"))


async def upsert_contact(session: AsyncSession, txn: dict) -> str | None:
    contact = txn.get("p2p_contact")
    if txn.get("payment_type") != "p2p" or not contact:
        return None

    contact_id = contact.get("contact_id")
    if not contact_id:
        return None

    existing = await session.scalar(
        select(P2PContact).where(P2PContact.user_id == txn["user_id"], P2PContact.contact_id == contact_id)
    )
    if existing:
        existing.display_name = contact.get("display_name")
        existing.email = contact.get("email")
        existing.deleted_at = None
        return existing.contact_id

    session.add(
        P2PContact(
            user_id=txn["user_id"],
            contact_id=contact_id,
            display_name=contact.get("display_name"),
            email=contact.get("email"),
        )
    )
    return contact_id


async def record_transaction(txn: dict):
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(Transaction).where(Transaction.txn_id == txn["txn_id"]))
        if existing:
            return existing, False

        contact_id = await upsert_contact(session, txn)
        db_txn = Transaction(
            txn_id=txn["txn_id"],
            user_id=txn["user_id"],
            merchant_id=txn.get("merchant_id"),
            amount=txn["amount"],
            currency=txn.get("currency", "USD"),
            payment_type=txn.get("payment_type", "credit"),
            status=txn.get("status", "processed"),
            processor_status=txn.get("processor_status"),
            final_status=txn.get("final_status"),
            decision_reason=txn.get("decision_reason"),
            processing_stage=txn.get("processing_stage"),
            authenticated_subject=txn.get("authenticated_subject"),
            high_value=str(txn.get("high_value", False)).lower(),
            fraud_status=txn.get("fraud_status", "unknown"),
            fraud_reason=txn.get("fraud_reason"),
            trace_id=txn.get("trace_id", ""),
            idempotency_key=txn.get("idempotency_key", ""),
            processor_ref=txn.get("processor_ref"),
            payment_token=txn.get("payment_token"),
            masked_pan=txn.get("masked_pan"),
            pan_fingerprint=txn.get("pan_fingerprint"),
            p2p_contact_id=contact_id,
        )
        session.add(db_txn)
        await session.commit()
        await session.refresh(db_txn)
        return db_txn, True


async def get_transaction(txn_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(Transaction).where(Transaction.txn_id == txn_id))
        if not existing:
            return None
        return existing.to_dict()


async def get_contact(user_id: str, contact_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(P2PContact).where(P2PContact.user_id == user_id, P2PContact.contact_id == contact_id)
        )
        if not existing:
            return None
        return existing.to_dict()


async def delete_contact(user_id: str, contact_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(P2PContact).where(P2PContact.user_id == user_id, P2PContact.contact_id == contact_id)
        )
        if not existing:
            return None
        existing.display_name = None
        existing.email = None
        existing.deleted_at = datetime.datetime.utcnow()
        await session.commit()
        await session.refresh(existing)
        return existing.to_dict()
