import asyncio
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import time
from shared.config import env_float, env_int, env_text

KAFKA_BOOTSTRAP = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "payment-initiated"
OUTPUT_TOPIC = "payment-processed"
DLQ_TOPIC = "payment-processed-dlq"
MAX_PROCESSING_RETRIES = env_int("MAX_PROCESSING_RETRIES", 3)
KAFKA_OPERATION_TIMEOUT_SECONDS = env_float("KAFKA_OPERATION_TIMEOUT_SECONDS", 3.0)

producer = None


def log_event(event: str, **fields):
    print(json.dumps({"service": "payment-service", "event": event, "ts": time.time(), **fields}, sort_keys=True))


async def wait_for_kafka_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            consumer = AIOKafkaConsumer(
                INPUT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="payment-service-readiness",
                auto_offset_reset="earliest",
            )
            await consumer.start()
            await consumer.stop()
            print("Payment service Kafka readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Kafka for payment-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for payment-service")

async def get_producer():
    global producer
    if producer is None:
        for attempt in range(1, 11):
            try:
                producer = AIOKafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP,
                    value_serializer=lambda v: json.dumps(v).encode(),
                    acks="all",
                    enable_idempotence=True,
                )
                await producer.start()
                break
            except Exception as exc:
                print(f"Waiting for Kafka producer in payment-service (attempt {attempt}/10): {exc}")
                await asyncio.sleep(2)
        else:
            raise RuntimeError("Kafka producer did not become ready for payment-service")
    return producer

async def process_transaction(txn: dict):
    result = dict(txn)
    result.pop("card_pan", None)
    result["processor_ref"] = f"ref_{txn['txn_id']}"
    result["processing_stage"] = "processor"
    result["high_value"] = txn["amount"] >= 1000

    if txn["amount"] <= 0:
        result["status"] = "declined"
        result["processor_status"] = "rejected"
        result["final_status"] = "declined"
        result["decision_reason"] = "Amount must be positive"
        return result

    supported_payment_types = {"credit", "p2p", "b2b"}
    if txn.get("payment_type") not in supported_payment_types:
        result["status"] = "declined"
        result["processor_status"] = "rejected"
        result["final_status"] = "declined"
        result["decision_reason"] = "Unsupported payment type"
        return result

    if txn.get("payment_type") == "p2p" and txn["amount"] > 2000:
        result["status"] = "declined"
        result["processor_status"] = "rejected"
        result["final_status"] = "declined"
        result["decision_reason"] = "P2P amount exceeds limit"
        return result

    result["status"] = "accepted"
    result["processor_status"] = "approved"
    result["final_status"] = "pending_fraud_review"
    result["decision_reason"] = "Accepted by processor, pending fraud review"
    return result


async def publish_to_topic(topic: str, key: str, payload: dict):
    prod = await get_producer()
    headers = [
        ("trace_id", payload.get("trace_id", "").encode()),
        ("idempotency_key", payload.get("idempotency_key", "").encode()),
    ]
    await asyncio.wait_for(
        prod.send_and_wait(topic, key=key.encode(), value=payload, headers=headers),
        timeout=KAFKA_OPERATION_TIMEOUT_SECONDS,
    )


async def publish_dlq(txn: dict, error: str, attempts: int):
    dlq_payload = {
        "source_topic": INPUT_TOPIC,
        "failed_topic": OUTPUT_TOPIC,
        "txn_id": txn.get("txn_id"),
        "trace_id": txn.get("trace_id"),
        "idempotency_key": txn.get("idempotency_key"),
        "attempts": attempts,
        "error": error,
        "payload": txn,
    }
    await publish_to_topic(DLQ_TOPIC, txn.get("txn_id", "unknown"), dlq_payload)
    log_event("payment_sent_to_dlq", txn_id=txn.get("txn_id"), attempts=attempts, error=error)

async def consume():
    await wait_for_kafka_ready()
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="payment-service-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log_event("payment_consumer_started", input_topic=INPUT_TOPIC, output_topic=OUTPUT_TOPIC)
    try:
        async for msg in consumer:
            txn = json.loads(msg.value)
            attempts = 0
            while True:
                try:
                    attempts += 1
                    log_event("payment_received", txn_id=txn["txn_id"], attempts=attempts)
                    result = await process_transaction(txn)
                    await publish_to_topic(OUTPUT_TOPIC, txn["txn_id"], result)
                    await consumer.commit()
                    log_event(
                        "payment_processed",
                        txn_id=txn["txn_id"],
                        status=result["status"],
                        final_status=result.get("final_status"),
                    )
                    break
                except Exception as exc:
                    log_event("payment_processing_failed", txn_id=txn.get("txn_id"), attempts=attempts, error=str(exc))
                    if attempts >= MAX_PROCESSING_RETRIES:
                        await publish_dlq(txn, str(exc), attempts)
                        await consumer.commit()
                        break
                    await asyncio.sleep(min(2 ** attempts, 5))
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())
