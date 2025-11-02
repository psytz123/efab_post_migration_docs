"""Integration with the event backbone (Kafka/Redpanda)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:  # pragma: no cover - optional dependency
    from aiokafka import AIOKafkaProducer
except ImportError:  # pragma: no cover - handled gracefully
    AIOKafkaProducer = None  # type: ignore


MEMORY_SCHEME = "memory://"


@dataclass
class OrderEvent:
    event_type: str
    order_id: str
    site_id: str
    payload: Dict[str, Any]
    ts: str = datetime.now(timezone.utc).isoformat()

    def to_message(self) -> Dict[str, Any]:
        return asdict(self)


class EventPublisher:
    """Kafka-backed publisher with in-memory fallback for tests."""

    def __init__(self, bootstrap_servers: Optional[str]) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer: Optional[AIOKafkaProducer] = None
        self._buffer: list[Dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return bool(self.bootstrap_servers) and self.bootstrap_servers != MEMORY_SCHEME

    async def start(self) -> None:
        if not self.enabled:
            return
        if AIOKafkaProducer is None:
            raise RuntimeError("aiokafka is not installed; unable to start Kafka publisher")
        self._producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def publish(self, event: OrderEvent) -> None:
        message = event.to_message()
        if self._producer is None:
            self._buffer.append(message)
            return

        payload = json.dumps(message).encode("utf-8")
        await self._producer.send_and_wait(event.event_type, payload)

    @property
    def buffer(self) -> list[Dict[str, Any]]:
        return self._buffer


def get_event_publisher(bootstrap_servers: Optional[str]) -> EventPublisher:
    return EventPublisher(bootstrap_servers)
