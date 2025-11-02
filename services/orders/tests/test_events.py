import asyncio

import pytest

from services.orders.app.events import EventPublisher, OrderEvent, get_event_publisher


@pytest.mark.asyncio
async def test_memory_publisher_buffers_events():
    publisher = EventPublisher(bootstrap_servers=None)
    event = OrderEvent(event_type="orders.created", order_id="ABC", site_id="bk", payload={})

    await publisher.publish(event)

    assert len(publisher.buffer) == 1
    assert publisher.buffer[0]["order_id"] == "ABC"


@pytest.mark.asyncio
async def test_get_event_publisher_uses_memory_scheme():
    publisher = get_event_publisher("memory://")
    await publisher.start()  # should be no-op
    await publisher.publish(OrderEvent("orders.updated", "XYZ", "bk", {}))

    assert publisher.buffer and publisher.buffer[0]["event_type"] == "orders.updated"


@pytest.mark.asyncio
async def test_start_raises_when_aiokafka_missing(monkeypatch):
    publisher = EventPublisher("kafka://localhost:9092")
    monkeypatch.setattr("services.orders.app.events.AIOKafkaProducer", None)
    with pytest.raises(RuntimeError):
        await publisher.start()
