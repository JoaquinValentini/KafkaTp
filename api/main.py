import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shared.db import Store
from shared.events import new_event, utc_now
from shared.kafka import config, ensure_topics, publish

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [API] %(message)s")
log = logging.getLogger("api")
producer: Producer | None = None
store: Store | None = None


class OrderRequest(BaseModel):
    customer: str = Field(min_length=1, max_length=120)
    product: str = Field(min_length=1, max_length=120)
    quantity: int = Field(gt=0, le=1000)
    price: float = Field(gt=0, le=100_000_000)
    payment_decision: str = Field(default="APPROVED", pattern="^(APPROVED|REJECTED)$")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    global producer, store
    ensure_topics()
    producer = Producer(config())
    store = Store(os.getenv("DATABASE_PATH", "data/orders.sqlite3"))
    log.info("API lista")
    yield
    producer.flush(5)


app = FastAPI(title="Kafka Orders TP", version="1.0.0", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def frontend() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.get("/api/orders")
@app.get("/orders")
async def orders() -> list[dict]:
    return store.all() if store else []


@app.post("/api/orders", status_code=202)
@app.post("/orders", status_code=202)
async def create_order(order: OrderRequest) -> dict:
    if producer is None or store is None:
        raise HTTPException(503, "API todavía no está lista")
    order_id = f"ORD-{uuid4().hex[:8].upper()}"
    timestamp = utc_now()
    payload = {"id": order_id, **order.model_dump(), "status": "CREATED"}
    event = new_event("order.created", payload)
    try:
        store.create_order(payload, timestamp)
        publish(producer, "orders", event)
        producer.flush(5)
        log.info("Pedido %s publicado en orders", order_id)
        return {"order_id": order_id, "status": "CREATED", "event_id": event["event_id"]}
    except Exception as exc:
        log.exception("No se pudo publicar el pedido %s", order_id)
        raise HTTPException(503, "No se pudo publicar el pedido") from exc


@app.get("/api/status")
async def status() -> dict[str, object]:
    return {
        "orders": store.all() if store else [],
        "payments_paused": store.is_service_paused("payments") if store else False,
        "notifications_paused": store.is_service_paused("notifications") if store else False,
    }


@app.post("/api/services/payments/pause")
async def pause_payments() -> dict[str, object]:
    if store is None:
        raise HTTPException(503, "API todavía no está lista")
    store.set_service_paused("payments", True)
    log.info("Consumidor de pagos pausado desde la interfaz")
    return {"service": "payments", "paused": True}


@app.post("/api/services/payments/resume")
async def resume_payments() -> dict[str, object]:
    if store is None:
        raise HTTPException(503, "API todavía no está lista")
    store.set_service_paused("payments", False)
    log.info("Consumidor de pagos reanudado desde la interfaz")
    return {"service": "payments", "paused": False}


@app.post("/api/services/notifications/pause")
async def pause_notifications() -> dict[str, object]:
    if store is None:
        raise HTTPException(503, "API todavía no está lista")
    store.set_service_paused("notifications", True)
    log.info("Consumidor de notificaciones pausado desde la interfaz")
    return {"service": "notifications", "paused": True}


@app.post("/api/services/notifications/resume")
async def resume_notifications() -> dict[str, object]:
    if store is None:
        raise HTTPException(503, "API todavía no está lista")
    store.set_service_paused("notifications", False)
    log.info("Consumidor de notificaciones reanudado desde la interfaz")
    return {"service": "notifications", "paused": False}


@app.delete("/api/orders")
async def clear_orders() -> dict[str, str]:
    if store is None:
        raise HTTPException(503, "API todavía no está lista")
    store.clear()
    log.info("Demo limpiada desde la interfaz")
    return {"message": "Demo limpiada"}
