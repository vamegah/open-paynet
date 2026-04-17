import asyncio
from aiokafka import AIOKafkaProducer
import json
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from .config import settings
from .observability import (
    PAYMENT_CIRCUIT_BREAKER_REJECTIONS,
    PAYMENT_EVENTS_FAILED,
    PAYMENT_EVENTS_PUBLISHED,
    PAYMENT_EVENTS_TIMED_OUT,
    log_event,
)

producer = None
payment_publish_breaker = CircuitBreaker(
    failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    reset_timeout_seconds=settings.CIRCUIT_BREAKER_RESET_TIMEOUT_SECONDS,
)

async def get_producer():
    global producer
    if producer is None:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",
            enable_idempotence=True,
        )
        await producer.start()
    return producer


async def reset_producer() -> None:
    global producer
    if producer is None:
        return
    try:
        await producer.stop()
    finally:
        producer = None


async def produce_event(key: str, value: dict):
    payment_publish_breaker.before_call()
    prod = await get_producer()
    headers = [
        ("trace_id", value.get("trace_id", "").encode()),
        ("idempotency_key", value.get("idempotency_key", "").encode()),
    ]
    try:
        await asyncio.wait_for(
            prod.send_and_wait(
                settings.KAFKA_PAYMENT_TOPIC,
                key=key.encode(),
                value=value,
                headers=headers,
            ),
            timeout=settings.EVENT_PUBLISH_TIMEOUT_SECONDS,
        )
        PAYMENT_EVENTS_PUBLISHED.inc()
        payment_publish_breaker.record_success()
        log_event(
            "api-gateway",
            "payment_event_published",
            txn_id=value.get("txn_id"),
            trace_id=value.get("trace_id"),
            topic=settings.KAFKA_PAYMENT_TOPIC,
            circuit_state=payment_publish_breaker.state(),
        )
    except asyncio.TimeoutError:
        PAYMENT_EVENTS_TIMED_OUT.inc()
        PAYMENT_EVENTS_FAILED.inc()
        payment_publish_breaker.record_failure()
        await reset_producer()
        log_event(
            "api-gateway",
            "payment_event_publish_timed_out",
            txn_id=value.get("txn_id"),
            trace_id=value.get("trace_id"),
            topic=settings.KAFKA_PAYMENT_TOPIC,
            circuit_state=payment_publish_breaker.state(),
        )
        raise
    except CircuitBreakerOpenError:
        PAYMENT_CIRCUIT_BREAKER_REJECTIONS.inc()
        log_event(
            "api-gateway",
            "payment_event_publish_rejected",
            txn_id=value.get("txn_id"),
            trace_id=value.get("trace_id"),
            topic=settings.KAFKA_PAYMENT_TOPIC,
            circuit_state=payment_publish_breaker.state(),
        )
        raise
    except Exception:
        PAYMENT_EVENTS_FAILED.inc()
        payment_publish_breaker.record_failure()
        await reset_producer()
        log_event(
            "api-gateway",
            "payment_event_publish_failed",
            txn_id=value.get("txn_id"),
            trace_id=value.get("trace_id"),
            topic=settings.KAFKA_PAYMENT_TOPIC,
            circuit_state=payment_publish_breaker.state(),
        )
        raise
