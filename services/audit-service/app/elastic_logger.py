import asyncio
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from elasticsearch import AsyncElasticsearch
import time
from shared.config import env_flag, env_float, env_int, env_text

KAFKA_BOOTSTRAP = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "fraud-evaluated"
ES_HOST = env_text("ELASTICSEARCH_HOST", "http://localhost:9200")
ES_USERNAME = env_text("ELASTICSEARCH_USERNAME")
ES_PASSWORD = env_text("ELASTICSEARCH_PASSWORD")
ES_VERIFY_CERTS = env_flag("ELASTICSEARCH_VERIFY_CERTS", True)
DLQ_TOPIC = "audit-dlq"
MAX_PROCESSING_RETRIES = env_int("MAX_PROCESSING_RETRIES", 3)
KAFKA_OPERATION_TIMEOUT_SECONDS = env_float("KAFKA_OPERATION_TIMEOUT_SECONDS", 3.0)
ELASTICSEARCH_OPERATION_TIMEOUT_SECONDS = env_float("ELASTICSEARCH_OPERATION_TIMEOUT_SECONDS", 3.0)
producer = None


def log_event(event: str, **fields):
    print(json.dumps({"service": "audit-service", "event": event, "ts": time.time(), **fields}, sort_keys=True))


def build_es_client() -> AsyncElasticsearch:
    kwargs = {"hosts": [ES_HOST], "verify_certs": ES_VERIFY_CERTS}
    if ES_USERNAME and ES_PASSWORD:
        kwargs["basic_auth"] = (ES_USERNAME, ES_PASSWORD)
    return AsyncElasticsearch(**kwargs)


async def wait_for_elasticsearch_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        es = build_es_client()
        try:
            if await es.ping():
                print("Audit service Elasticsearch readiness confirmed")
                await es.close()
                return
        except Exception as exc:
            print(f"Waiting for Elasticsearch for audit-service (attempt {attempt}/{max_attempts}): {exc}")
        finally:
            await es.close()
        await asyncio.sleep(delay_seconds)
    raise RuntimeError("Elasticsearch did not become ready for audit-service")


async def wait_for_kafka_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        consumer = AIOKafkaConsumer(
            INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id="audit-readiness",
            auto_offset_reset="earliest",
        )
        try:
            await consumer.start()
            await consumer.stop()
            print("Audit service Kafka readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Kafka for audit-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for audit-service")


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
    log_event("audit_sent_to_dlq", txn_id=txn.get("txn_id"), attempts=attempts, error=error)

async def consume():
    await wait_for_elasticsearch_ready()
    await wait_for_kafka_ready()
    es = build_es_client()
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="audit-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log_event("audit_consumer_started", input_topic=INPUT_TOPIC)
    try:
        async for msg in consumer:
            txn = json.loads(msg.value)
            attempts = 0
            while True:
                try:
                    attempts += 1
                    await asyncio.wait_for(
                        es.index(index="payment_audit", id=txn["txn_id"], document=txn),
                        timeout=ELASTICSEARCH_OPERATION_TIMEOUT_SECONDS,
                    )
                    await consumer.commit()
                    log_event("audit_indexed", txn_id=txn["txn_id"], trace_id=txn.get("trace_id"))
                    break
                except Exception as exc:
                    log_event("audit_failed", txn_id=txn.get("txn_id"), attempts=attempts, error=str(exc))
                    if attempts >= MAX_PROCESSING_RETRIES:
                        await publish_dlq(txn, str(exc), attempts)
                        await consumer.commit()
                        break
                    await asyncio.sleep(min(2 ** attempts, 5))
    finally:
        await consumer.stop()
        await es.close()

if __name__ == "__main__":
    asyncio.run(consume())
