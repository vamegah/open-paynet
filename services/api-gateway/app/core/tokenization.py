import hashlib
import hmac
import re

from fastapi import HTTPException

from .config import settings


PAN_PATTERN = re.compile(r"^\d{12,19}$")


def tokenize_pan(card_pan: str) -> dict[str, str]:
    normalized = card_pan.replace(" ", "").replace("-", "")
    if not PAN_PATTERN.match(normalized):
        raise HTTPException(status_code=400, detail="Invalid PAN format")

    digest = hmac.new(
        settings.TOKENIZATION_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    last4 = normalized[-4:]
    return {
        "payment_token": f"tok_{digest[:24]}",
        "masked_pan": f"**** **** **** {last4}",
        "pan_fingerprint": digest,
    }
