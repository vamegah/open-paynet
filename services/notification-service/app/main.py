import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .notifier import consume, get_notification

consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    consumer_task = asyncio.create_task(consume())
    try:
        yield
    finally:
        if consumer_task is not None:
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="OpenPayNet Notification Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/notifications/{txn_id}")
async def read_notification(txn_id: str):
    notification = await get_notification(txn_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification
