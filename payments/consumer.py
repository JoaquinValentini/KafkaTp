import json
import logging
import os

from confluent_kafka import Producer

from shared.db import Store
from shared.events import new_event, utc_now
from shared.kafka import config, consume_forever, ensure_topics, publish

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [PAYMENTS] %(message)s")
log = logging.getLogger("payments")
store = Store(os.getenv("DATABASE_PATH", "data/orders.sqlite3"))
producer = Producer(config())


def handle(event: dict) -> None:
    payload = event.get("payload", {})
    order_id = payload.get("id")
    if not order_id:
        raise ValueError("evento sin payload.id")
    log.info("Pedido %s recibido", order_id)
    decision = payload.get("payment_decision", "APPROVED")
    payment_status = "PAYMENT_APPROVED" if decision == "APPROVED" else "PAYMENT_REJECTED"
    timestamp = utc_now()
    store.update_status(order_id, payment_status, timestamp)
    payment = {
        "order_id": order_id,
        "amount": payload["price"] * payload["quantity"],
        "status": payment_status,
    }
    publish(producer, "payments", new_event("payment.result", payment))
    producer.flush(5)
    log.info("%s para pedido %s", "Pago aprobado" if decision == "APPROVED" else "Pago rechazado", order_id)


if __name__ == "__main__":
    ensure_topics()
    consume_forever("payments-service", "orders", handle, lambda: store.is_service_paused("payments"))
