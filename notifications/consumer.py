import logging
import os

from confluent_kafka import Producer

from shared.db import Store
from shared.events import new_event, utc_now
from shared.kafka import config, consume_forever, ensure_topics, publish

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [NOTIFICATIONS] %(message)s")
log = logging.getLogger("notifications")
store = Store(os.getenv("DATABASE_PATH", "data/orders.sqlite3"))
producer = Producer(config())


def handle(event: dict) -> None:
    payment = event.get("payload", {})
    order_id = payment.get("order_id")
    if not order_id:
        raise ValueError("evento de pago sin order_id")
    timestamp = utc_now()
    store.update_status(order_id, "NOTIFICATION_SENT", timestamp)
    notification = {
        "order_id": order_id,
        "payment_status": payment.get("status"),
        "message": f"Pago {payment.get('status')} para pedido {order_id}",
    }
    publish(producer, "notifications", new_event("notification.created", notification))
    producer.flush(5)
    log.info("Notificación generada para pedido %s", order_id)


if __name__ == "__main__":
    ensure_topics()
    consume_forever(
        "notifications-service",
        "payments",
        handle,
        lambda: store.is_service_paused("notifications"),
    )
