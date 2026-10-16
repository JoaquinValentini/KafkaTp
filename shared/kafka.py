import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

from confluent_kafka import Consumer, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from shared.events import TOPICS

log = logging.getLogger(__name__)


def config() -> dict[str, Any]:
    return {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "client.id": os.getenv("SERVICE_NAME", "kafka-tp"),
    }


def ensure_topics(timeout: float = 60) -> None:
    admin = AdminClient(config())
    deadline = time.monotonic() + timeout
    while True:
        try:
            futures = admin.create_topics([NewTopic(t, num_partitions=1, replication_factor=1) for t in TOPICS])
            for topic, future in futures.items():
                try:
                    future.result()
                    log.info("Topic creado: %s", topic)
                except Exception as exc:
                    if "already exists" not in str(exc).lower():
                        raise
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Kafka no disponible: {exc}") from exc
            log.warning("Esperando Kafka (%s)", exc)
            time.sleep(2)


def publish(producer: Producer, topic: str, event: dict[str, Any]) -> None:
    producer.produce(topic, json.dumps(event).encode(), key=event["payload"].get("id", event["event_id"]).encode())
    producer.poll(0)


def consume_forever(
    group: str,
    topic: str,
    handler: Callable[[dict[str, Any]], None],
    pause_check: Callable[[], bool] | None = None,
) -> None:
    consumer = Consumer({**config(), "group.id": group, "auto.offset.reset": "earliest", "enable.auto.commit": False})
    consumer.subscribe([topic])
    pending_message = None
    try:
        while True:
            if pending_message is None:
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    log.error("Kafka error: %s", message.error())
                    continue
                pending_message = message
            if pause_check and pause_check():
                time.sleep(0.5)
                continue
            message = pending_message
            pending_message = None
            try:
                handler(json.loads(message.value()))
                consumer.commit(message=message, asynchronous=False)
            except Exception:
                log.exception("No se pudo procesar mensaje; se reintentará")
    finally:
        consumer.close()
