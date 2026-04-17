from fastapi import APIRouter, Depends, HTTPException, Request
from ..models.payment import PaymentRequest, PaymentResponse
from ..core.auth import AuthContext, require_auth
from ..core.circuit_breaker import CircuitBreakerOpenError
from ..core.idempotency import cache_response, get_cached_response
from ..core.kafka_producer import produce_event
from ..core.observability import log_event
from ..core.rate_limiter import rate_limit
from ..core.tokenization import tokenize_pan

router = APIRouter()

@router.post("/v1/payments", response_model=PaymentResponse)
@rate_limit(requests=10, period=60)
async def process_payment(
    request: Request,
    payment: PaymentRequest,
    auth_context: AuthContext = Depends(
        require_auth(required_scopes={"payments:write"}, allowed_roles={"payment_initiator", "merchant", "admin"})
    ),
):
    if payment.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if auth_context.merchant_id and payment.merchant_id and payment.merchant_id != auth_context.merchant_id:
        raise HTTPException(status_code=403, detail="Merchant ID does not match API key")
    if payment.card_pan and payment.payment_token:
        raise HTTPException(status_code=400, detail="Provide either card_pan or payment_token, not both")

    cached = await get_cached_response(payment.idempotency_key)
    if cached:
        log_event(
            "api-gateway",
            "idempotency_cache_hit",
            txn_id=payment.txn_id,
            trace_id=cached.get("trace_id"),
            idempotency_key=payment.idempotency_key,
        )
        return PaymentResponse(**cached)

    trace_id = payment.trace_id or request.state.trace_id
    event_payload = payment.model_dump()
    tokenized = False
    if payment.card_pan:
        tokenized_fields = tokenize_pan(payment.card_pan)
        event_payload.update(tokenized_fields)
        event_payload["card_pan"] = None
        tokenized = True

    event_payload["trace_id"] = trace_id
    event_payload["authenticated_subject"] = auth_context.subject

    try:
        await produce_event(payment.txn_id, event_payload)
    except CircuitBreakerOpenError as exc:
        raise HTTPException(status_code=503, detail="Payment processing temporarily unavailable") from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Payment processing timed out") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Payment event publish failed") from exc
    log_event(
        "api-gateway",
        "payment_queued",
        txn_id=payment.txn_id,
        trace_id=trace_id,
        merchant_id=payment.merchant_id,
        payment_type=payment.payment_type,
    )

    response_payload = {
        "status": "accepted",
        "processing_stage": "queued",
        "txn_id": payment.txn_id,
        "trace_id": trace_id,
        "payment_type": payment.payment_type,
        "merchant_id": payment.merchant_id,
        "authenticated_subject": auth_context.subject,
        "payment_token": event_payload.get("payment_token"),
        "tokenized": tokenized or bool(event_payload.get("payment_token")),
        "message": "Queued for asynchronous processing",
    }
    await cache_response(payment.idempotency_key, response_payload)
    return PaymentResponse(**response_payload)
