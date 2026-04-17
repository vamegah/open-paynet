import json
import asyncio
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
import redis.asyncio as redis
import time
from shared.config import env_float, env_int, env_text

REDIS_URL = env_text("REDIS_URL", "redis://localhost:6379")
KAFKA_BOOTSTRAP = env_text("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = "payment-processed"
OUTPUT_TOPIC = "fraud-evaluated"
DLQ_TOPIC = "fraud-evaluated-dlq"
MAX_PROCESSING_RETRIES = env_int("MAX_PROCESSING_RETRIES", 3)
KAFKA_OPERATION_TIMEOUT_SECONDS = env_float("KAFKA_OPERATION_TIMEOUT_SECONDS", 3.0)
BAD_IP_ADDRESSES = {
    item.strip()
    for item in env_text("BAD_IP_ADDRESSES", "10.0.0.13,203.0.113.66").split(",")
    if item.strip()
}
GEO_MISMATCH_THRESHOLD_KM = env_float("GEO_MISMATCH_THRESHOLD_KM", 500.0)

redis_client = None
producer = None


def log_event(event: str, **fields):
    print(json.dumps({"service": "fraud-service", "event": event, "ts": time.time(), **fields}, sort_keys=True))


async def wait_for_redis_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            client = await redis.from_url(REDIS_URL, decode_responses=True)
            await client.ping()
            await client.aclose()
            print("Fraud service Redis readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Redis for fraud-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Redis did not become ready for fraud-service")


async def wait_for_kafka_ready(max_attempts: int = 20, delay_seconds: int = 3):
    for attempt in range(1, max_attempts + 1):
        try:
            consumer = AIOKafkaConsumer(
                INPUT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="fraud-readiness",
                auto_offset_reset="earliest",
            )
            await consumer.start()
            await consumer.stop()
            print("Fraud service Kafka readiness confirmed")
            return
        except Exception as exc:
            print(f"Waiting for Kafka for fraud-service (attempt {attempt}/{max_attempts}): {exc}")
            await asyncio.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for fraud-service")

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

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
                print(f"Waiting for Kafka producer in fraud-service (attempt {attempt}/10): {exc}")
                await asyncio.sleep(2)
        else:
            raise RuntimeError("Kafka producer did not become ready for fraud-service")
    return producer

async def velocity_check(user_id: str, txn_time: datetime) -> bool:
    r = await get_redis()
    key = f"txn_count:{user_id}"
    # In production, store timestamps in sorted set; simplified:
    count = await r.get(key) or 0
    if int(count) >= 5:
        return True  # suspicious
    await r.incr(key)
    await r.expire(key, 60)
    return False


def calculate_distance_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    earth_radius_km = 6371.0
    lat1, lon1 = origin
    lat2, lon2 = destination
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))


async def ip_reputation_check(ip_address: str | None) -> bool:
    if not ip_address:
        return False
    return ip_address in BAD_IP_ADDRESSES


async def geo_mismatch_check(user_id: str, lat_lon: list[float] | tuple[float, float] | None) -> bool:
    if not lat_lon:
        return False

    r = await get_redis()
    key = f"user_last_location:{user_id}"
    previous = await r.get(key)
    current_location = f"{lat_lon[0]},{lat_lon[1]}"
    await r.set(key, current_location, ex=86400)

    if not previous:
        return False

    previous_lat, previous_lon = map(float, previous.split(","))
    distance = calculate_distance_km((previous_lat, previous_lon), (lat_lon[0], lat_lon[1]))
    return distance > GEO_MISMATCH_THRESHOLD_KM

async def evaluate_fraud(txn: dict) -> dict:
    if txn.get("final_status") == "declined":
        txn["fraud_suspicious"] = False
        txn["fraud_reason"] = ""
        txn["fraud_status"] = "skipped"
        txn["processing_stage"] = "completed"
        return txn

    user_id = txn["user_id"]
    txn_time = datetime.utcnow()
    suspicious = False
    reason = ""
    
    # Velocity rule
    if await velocity_check(user_id, txn_time):
        suspicious = True
        reason = "Velocity exceeded (5+ txn/min)"

    # Geo rule (mock: if lat_lon missing and amount > 1000)
    if not suspicious and txn.get("lat_lon") is None and txn["amount"] > 1000:
        suspicious = True
        reason = "High amount without location data"

    if not suspicious and await geo_mismatch_check(user_id, txn.get("lat_lon")):
        suspicious = True
        reason = "Geo mismatch detected"

    if not suspicious and await ip_reputation_check(txn.get("ip_address")):
        suspicious = True
        reason = "High-risk IP reputation"

    txn["fraud_suspicious"] = suspicious
    txn["fraud_reason"] = reason
    txn["fraud_status"] = "flagged" if suspicious else "cleared"
    txn["processing_stage"] = "completed"
    if suspicious:
        txn["status"] = "declined"
        txn["final_status"] = "declined"
        txn["decision_reason"] = reason
    else:
        txn["status"] = "approved"
        txn["final_status"] = "approved"
        txn["decision_reason"] = "Approved after fraud evaluation"
    return txn


async def already_processed(txn_id: str) -> bool:
    r = await get_redis()
    return bool(await r.get(f"fraud_processed:{txn_id}"))


async def mark_processed(txn_id: str):
    r = await get_redis()
    await r.set(f"fraud_processed:{txn_id}", "1", ex=86400)


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
        "attempts": attempts,
        "error": error,
        "payload": txn,
    }
    await publish_to_topic(DLQ_TOPIC, txn.get("txn_id", "unknown"), dlq_payload)
    log_event("fraud_sent_to_dlq", txn_id=txn.get("txn_id"), attempts=attempts, error=error)

async def consume():
    await wait_for_redis_ready()
    await wait_for_kafka_ready()
    consumer = AIOKafkaConsumer(
        INPUT_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="fraud-group",
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    await consumer.start()
    log_event("fraud_consumer_started", input_topic=INPUT_TOPIC, output_topic=OUTPUT_TOPIC)
    try:
        async for msg in consumer:
            txn = json.loads(msg.value)
            txn_id = txn["txn_id"]
            if await already_processed(txn_id):
                log_event("fraud_duplicate_skipped", txn_id=txn_id)
                await consumer.commit()
                continue

            attempts = 0
            while True:
                try:
                    attempts += 1
                    evaluated = await evaluate_fraud(txn)
                    await publish_to_topic(OUTPUT_TOPIC, txn_id, evaluated)
                    await mark_processed(txn_id)
                    await consumer.commit()
                    log_event(
                        "fraud_evaluated",
                        txn_id=txn_id,
                        fraud_status=evaluated["fraud_status"],
                        final_status=evaluated.get("final_status"),
                    )
                    break
                except Exception as exc:
                    log_event("fraud_processing_failed", txn_id=txn_id, attempts=attempts, error=str(exc))
                    if attempts >= MAX_PROCESSING_RETRIES:
                        await publish_dlq(txn, str(exc), attempts)
                        await consumer.commit()
                        break
                    await asyncio.sleep(min(2 ** attempts, 5))
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(consume())
