import json
import time

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "openpaynet_gateway_requests_total",
    "Total API gateway requests",
    ["method", "path", "status"],
)
PAYMENT_EVENTS_PUBLISHED = Counter(
    "openpaynet_gateway_payment_events_published_total",
    "Total payment events published by the API gateway",
)
PAYMENT_EVENTS_FAILED = Counter(
    "openpaynet_gateway_payment_events_failed_total",
    "Total failed payment event publish attempts by the API gateway",
)
PAYMENT_EVENTS_TIMED_OUT = Counter(
    "openpaynet_gateway_payment_events_timed_out_total",
    "Total timed out payment event publish attempts by the API gateway",
)
PAYMENT_CIRCUIT_BREAKER_REJECTIONS = Counter(
    "openpaynet_gateway_payment_circuit_breaker_rejections_total",
    "Total requests rejected because the payment event circuit breaker was open",
)
REQUEST_LATENCY = Histogram(
    "openpaynet_gateway_request_latency_seconds",
    "Gateway request latency in seconds",
    ["method", "path"],
)


def log_event(service: str, event: str, **fields):
    payload = {
        "service": service,
        "event": event,
        "ts": time.time(),
        **fields,
    }
    print(json.dumps(payload, sort_keys=True))


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
