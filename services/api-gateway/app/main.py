import uuid

from fastapi import FastAPI
from .core.observability import REQUEST_COUNT, REQUEST_LATENCY, log_event, metrics_response
from .routes import payments

app = FastAPI(title="OpenPayNet API Gateway")
app.include_router(payments.router)


@app.middleware("http")
async def propagate_trace_id(request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    method = request.method
    path = request.url.path
    with REQUEST_LATENCY.labels(method=method, path=path).time():
        response = await call_next(request)
    REQUEST_COUNT.labels(method=method, path=path, status=str(response.status_code)).inc()
    log_event(
        "api-gateway",
        "http_request_completed",
        method=method,
        path=path,
        status_code=response.status_code,
        trace_id=trace_id,
    )
    response.headers["x-trace-id"] = trace_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["cross-origin-resource-policy"] = "same-origin"
    return response

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return metrics_response()
