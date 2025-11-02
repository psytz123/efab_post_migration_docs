#!/usr/bin/env python3
"""Prometheus exporter that polls the Orders dashboard metrics API."""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests
from prometheus_client import Gauge, start_http_server

ORDERS_BASE_URL = os.environ.get("ORDERS_BASE_URL", "http://host.docker.internal:8080")
EXPORTER_PORT = int(os.environ.get("EXPORTER_PORT", "9108"))
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", "10"))

TOTAL_ORDERS = Gauge("orders_total", "Total orders in the system")
ORDERS_LAST_24H = Gauge("orders_created_last_24h", "Orders created in the last 24h")
THROUGHPUT_PER_HOUR = Gauge("orders_throughput_per_hour", "Orders created per hour (24h window)")
STATE_COUNT = Gauge("orders_state_count", "Orders per state", ["state"])


def fetch_metrics() -> Dict[str, Any]:
    url = f"{ORDERS_BASE_URL}/dashboard/api/metrics"
    response = requests.get(url, timeout=5)
    response.raise_for_status()
    return response.json()


def update_gauges(payload: Dict[str, Any]) -> None:
    TOTAL_ORDERS.set(payload.get("total_orders", 0))
    ORDERS_LAST_24H.set(payload.get("orders_last_24h", 0))
    THROUGHPUT_PER_HOUR.set(payload.get("throughput_per_hour", 0.0))

    STATE_COUNT.clear()
    for state, count in payload.get("state_counts", {}).items():
        STATE_COUNT.labels(state=state).set(count)


def main() -> None:
    start_http_server(EXPORTER_PORT)
    while True:
        try:
            data = fetch_metrics()
            update_gauges(data)
        except Exception as exc:  # pragma: no cover - exporter robustness
            print(f"Exporter error: {exc}", flush=True)
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
