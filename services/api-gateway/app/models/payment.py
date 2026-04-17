from pydantic import BaseModel
from typing import Literal, Optional


class P2PContact(BaseModel):
    contact_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None


class PaymentRequest(BaseModel):
    txn_id: str
    user_id: str
    idempotency_key: str
    amount: float
    currency: str = "USD"
    payment_type: Literal["credit", "p2p", "b2b"] = "credit"
    merchant_id: Optional[str] = None
    trace_id: Optional[str] = None
    lat_lon: Optional[tuple[float, float]] = None
    ip_address: Optional[str] = None
    card_pan: Optional[str] = None
    payment_token: Optional[str] = None
    masked_pan: Optional[str] = None
    pan_fingerprint: Optional[str] = None
    p2p_contact: Optional[P2PContact] = None

class PaymentResponse(BaseModel):
    status: str
    processing_stage: str
    txn_id: str
    trace_id: str
    payment_type: Literal["credit", "p2p", "b2b"]
    merchant_id: Optional[str] = None
    authenticated_subject: Optional[str] = None
    payment_token: Optional[str] = None
    tokenized: bool = False
    message: str = ""
