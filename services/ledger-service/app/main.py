import asyncio

from fastapi import FastAPI, HTTPException

from .consumer import consume
from .db import delete_contact, get_contact, get_transaction, init_db
from .observability import metrics_response


app = FastAPI(title="OpenPayNet Ledger Service")
consumer_task = None


@app.on_event("startup")
async def startup() -> None:
    global consumer_task
    await init_db()
    consumer_task = asyncio.create_task(consume())


@app.on_event("shutdown")
async def shutdown() -> None:
    global consumer_task
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return metrics_response()


@app.get("/v1/ledger/{txn_id}")
async def fetch_transaction(txn_id: str) -> dict:
    transaction = await get_transaction(txn_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.get("/v1/contacts/{user_id}/{contact_id}")
async def fetch_contact(user_id: str, contact_id: str) -> dict:
    contact = await get_contact(user_id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@app.delete("/v1/contacts/{user_id}/{contact_id}")
async def gdpr_delete_contact(user_id: str, contact_id: str) -> dict:
    contact = await delete_contact(user_id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted", "contact": contact}
