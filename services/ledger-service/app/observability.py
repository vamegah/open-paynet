import json
import time

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

LEDGER_RECORDS_WRITTEN = Counter(
    "openpaynet_ledger_records_written_total",
    "Total transactions written to the ledger",
)
LEDGER_DUPLICATE_SKIPS = Counter(
    "openpaynet_ledger_duplicate_skips_total",
    "Total duplicate transactions ignored by the ledger",
)
LEDGER_CONSUMER_ERRORS = Counter(
    "openpaynet_ledger_consumer_errors_total",
    "Total ledger consumer processing errors",
)
LEDGER_DLQ_PUBLISHES = Counter(
    "openpaynet_ledger_dlq_publishes_total",
    "Total events sent to the ledger dead-letter topic",
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
