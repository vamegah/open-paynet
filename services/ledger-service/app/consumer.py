import asyncio
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from .db import engine, record_transaction, init_db
from .observability import (
    LEDGER_CONSUMER_ERRORS,
    LEDGER_DLQ_PUBLISHES,
    LEDGER_DUPLICATE_SKIPS,
    LEDGER_RECORDS_WRITTEN,
    log_event,
)
from shared.config import env_float, env_int, env_text

KAFKA_BOOTSTRAP = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "fraud-evaluated"
DLQ_TOPIC = "ledger-recording-dlq"
MAX_PROCESSING_RETRIES = env_int("MAX_PROCESSING_RETRIES", 3)
KAFKA_OPERATION_TIMEOUT_SECONDS = env_float("KAFKA_OPERATION_TIMEOUT_SECONDS", 3.0)
DATABASE_OPERATION_TIMEOUT_SECONDS = env_float("DATABASE_OPERATION_TIMEOUT_SECONDS", 3.0)
producer = None


async def wait_for_database_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            print("Ledger database readiness confirmed")
            return
        except SQLAlchemyError as exc:
            print(f"Waiting for ledger database (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Ledger database did not become ready")


async def wait_for_kafka_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        consumer = AIOKafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="ledger-readiness",
            auto_offset_reset="earliest",
        )
        try:
            await consumer.start()
            await consumer.stop()
            print("Ledger Kafka readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Kafka for ledger-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for ledger-service")


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
    LEDGER_DLQ_PUBLISHES.inc()
    log_event("ledger-service", "ledger_sent_to_dlq", txn_id=txn.get("txn_id"), attempts=attempts, error=error)

async def consume():
    await wait_for_database_ready()
    await init_db()
    await wait_for_kafka_ready()
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="ledger-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log_event("ledger-service", "ledger_consumer_started", input_topic=INPUT_TOPIC)
    try:
        async for msg in consumer:
            txn = json.loads(msg.value)
            attempts = 0
            while True:
                try:
                    attempts += 1
                    _, inserted = await asyncio.wait_for(
                        record_transaction(txn),
                        timeout=DATABASE_OPERATION_TIMEOUT_SECONDS,
                    )
                    if inserted:
                        LEDGER_RECORDS_WRITTEN.inc()
                        log_event("ledger-service", "ledger_recorded", txn_id=txn["txn_id"], trace_id=txn.get("trace_id"))
                    else:
                        LEDGER_DUPLICATE_SKIPS.inc()
                        log_event("ledger-service", "ledger_duplicate_skipped", txn_id=txn["txn_id"])
                    await consumer.commit()
                    break
                except Exception as exc:
                    LEDGER_CONSUMER_ERRORS.inc()
                    log_event("ledger-service", "ledger_record_failed", txn_id=txn.get("txn_id"), attempts=attempts, error=str(exc))
                    if attempts >= MAX_PROCESSING_RETRIES:
                        await publish_dlq(txn, str(exc), attempts)
                        await consumer.commit()
                        break
                    await asyncio.sleep(min(2 ** attempts, 5))
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())
