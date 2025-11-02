"""Observability helpers for the Orders service."""

from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

ORDER_CREATED_COUNTER_NAME = "orders_created_total"
ORDER_STATE_DENIED_COUNTER_NAME = "orders_state_transition_denied_total"


class Telemetry:
    def __init__(self, service_name: str) -> None:
        resource = Resource.create({"service.name": service_name})
        self.tracer_provider = TracerProvider(resource=resource)
        self.meter_provider = MeterProvider(resource=resource)

        trace.set_tracer_provider(self.tracer_provider)
        metrics.set_meter_provider(self.meter_provider)

        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)

        self.orders_created = self.meter.create_counter(
            name=ORDER_CREATED_COUNTER_NAME,
            description="Number of orders created",
        )
        self.orders_state_denied = self.meter.create_counter(
            name=ORDER_STATE_DENIED_COUNTER_NAME,
            description="Number of denied state transitions",
        )

    def record_order_created(self, site_id: str) -> None:
        self.orders_created.add(1, {"site_id": site_id})

    def record_state_denied(self, previous: str, attempted: str) -> None:
        self.orders_state_denied.add(1, {"from": previous, "to": attempted})


def setup_telemetry(service_name: str) -> Telemetry:
    return Telemetry(service_name=service_name)
