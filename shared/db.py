import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                customer TEXT NOT NULL,
                product TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                payment_decision TEXT NOT NULL,
                status TEXT NOT NULL,
                status_history TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
        )
        self.connection.commit()

    def create_order(self, order: dict[str, Any], timestamp: str) -> None:
        with self.lock:
            self.connection.execute(
                """INSERT INTO orders
                (id, customer, product, quantity, price, payment_decision,
                 status, status_history, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'CREATED', ?, ?)""",
                (
                    order["id"], order["customer"], order["product"],
                    order["quantity"], order["price"],
                    order["payment_decision"],
                    json.dumps([{"status": "CREATED", "at": timestamp}]),
                    timestamp,
                ),
            )
            self.connection.commit()

    def update_status(self, order_id: str, status: str, timestamp: str) -> None:
        with self.lock:
            row = self.connection.execute(
                "SELECT status_history FROM orders WHERE id = ?", (order_id,)
            ).fetchone()
            if row is None:
                return
            history = json.loads(row["status_history"])
            if not history or history[-1]["status"] != status:
                history.append({"status": status, "at": timestamp})
            self.connection.execute(
                "UPDATE orders SET status = ?, status_history = ?, updated_at = ? WHERE id = ?",
                (status, json.dumps(history), timestamp, order_id),
            )
            self.connection.commit()

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM orders ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["status_history"] = json.loads(item["status_history"])
            result.append(item)
        return result

    def clear(self) -> None:
        with self.lock:
            self.connection.execute("DELETE FROM orders")
            self.connection.commit()
