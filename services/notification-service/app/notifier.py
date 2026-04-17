import asyncio
import json
import time
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from redis import asyncio as redis

from shared.config import env_float, env_int, env_text

KAFKA_BOOTSTRAP = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = env_text("REDIS_URL", "redis://localhost:6379")
INPUT_TOPIC = "fraud-evaluated"
DLQ_TOPIC = "notification-dlq"
MAX_PROCESSING_RETRIES = env_int("MAX_PROCESSING_RETRIES", 3)
KAFKA_OPERATION_TIMEOUT_SECONDS = env_float("KAFKA_OPERATION_TIMEOUT_SECONDS", 3.0)
NOTIFICATION_TTL_SECONDS = env_int("NOTIFICATION_TTL_SECONDS", 86400)

producer = None
redis_client = None


def log_event(event: str, **fields):
    print(json.dumps({"service": "notification-service", "event": event, "ts": time.time(), **fields}, sort_keys=True))


def route_notification(txn: dict) -> dict | None:
    final_status = txn.get("final_status")
    is_high_value = str(txn.get("high_value", False)).lower() == "true" or txn.get("high_value") is True
    channels: list[str] = []
    template = None
    severity = "info"

    if final_status == "declined":
        channels.append("email")
        template = "payment-declined"
        severity = "high"

    if is_high_value:
        channels.append("slack")
        template = template or "high-value-payment"
        severity = "critical" if final_status == "declined" else "medium"

    unique_channels = sorted(set(channels))
    if not unique_channels:
        return None

    return {
        "txn_id": txn.get("txn_id"),
        "user_id": txn.get("user_id"),
        "merchant_id": txn.get("merchant_id"),
        "trace_id": txn.get("trace_id"),
        "payment_type": txn.get("payment_type"),
        "amount": txn.get("amount"),
        "currency": txn.get("currency", "USD"),
        "final_status": final_status,
        "decision_reason": txn.get("decision_reason", ""),
        "high_value": is_high_value,
        "channels": unique_channels,
        "template": template,
        "severity": severity,
        "status": "delivered",
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }


async def wait_for_redis_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            client = await redis.from_url(REDIS_URL, decode_responses=True)
            await client.ping()
            await client.aclose()
            print("Notification service Redis readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Redis for notification-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Redis did not become ready for notification-service")


async def wait_for_kafka_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        consumer = AIOKafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="notification-readiness",
            auto_offset_reset="earliest",
        )
        try:
            await consumer.start()
            await consumer.stop()
            print("Notification service Kafka readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Kafka for notification-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for notification-service")


async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client


async def get_notification(txn_id: str) -> dict | None:
    client = await get_redis()
    payload = await client.get(f"notification:{txn_id}")
    if not payload:
        return None
    return json.loads(payload)


async def store_notification(notification: dict):
    client = await get_redis()
    await client.set(f"notification:{notification['txn_id']}", json.dumps(notification), ex=NOTIFICATION_TTL_SECONDS)


async def mark_sent_if_new(txn_id: str) -> bool:
    client = await get_redis()
    return bool(await client.set(f"notification:sent:{txn_id}", "1", ex=NOTIFICATION_TTL_SECONDS, nx=True))


async def get_producer():
    global producer
    if producer is None:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode(),
            acks="all",
            enable_idempotence=True,
        )
        await producer.start()
    return producer


async def publish_dlq(txn: dict, error: str, attempts: int):
    prod = await get_producer()
    payload = {
        "source_topic": INPUT_TOPIC,
        "txn_id": txn.get("txn_id"),
        "trace_id": txn.get("trace_id"),
        "attempts": attempts,
        "error": error,
        "payload": txn,
    }
    await asyncio.wait_for(
        prod.send_and_wait(DLQ_TOPIC, key=txn.get("txn_id", "unknown").encode(), value=payload),
        timeout=KAFKA_OPERATION_TIMEOUT_SECONDS,
    )
    log_event("notification_sent_to_dlq", txn_id=txn.get("txn_id"), attempts=attempts, error=error)


async def process_notification(txn: dict):
    notification = route_notification(txn)
    if notification is None:
        return None

    if not await mark_sent_if_new(notification["txn_id"]):
        existing = await get_notification(notification["txn_id"])
        log_event("notification_duplicate_skipped", txn_id=notification["txn_id"])
        return existing

    await store_notification(notification)
    log_event(
        "notification_dispatched",
        txn_id=notification["txn_id"],
        user_id=notification["user_id"],
        channels=notification["channels"],
        template=notification["template"],
        severity=notification["severity"],
        status=notification["final_status"],
    )
    return notification


async def consume():
    await wait_for_redis_ready()
    await wait_for_kafka_ready()
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="notification-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log_event("notification_consumer_started", input_topic=INPUT_TOPIC)
    try:
        async for msg in consumer:
            txn = json.loads(msg.value)
            attempts = 0
            while True:
                try:
                    attempts += 1
                    await process_notification(txn)
                    await consumer.commit()
                    break
                except Exception as exc:
                    log_event("notification_failed", txn_id=txn.get("txn_id"), attempts=attempts, error=str(exc))
                    if attempts >= MAX_PROCESSING_RETRIES:
                        await publish_dlq(txn, str(exc), attempts)
                        await consumer.commit()
                        break
                    await asyncio.sleep(min(2 ** attempts, 5))
    finally:
        await consumer.stop()
