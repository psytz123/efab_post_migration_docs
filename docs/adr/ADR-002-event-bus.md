# ADR-002: Event Bus Selection
**Status:** Accepted • **Date:** 2025-11-01

Choose **Redpanda/Kafka** for durability and replay of task/telemetry events.
For very first simulator runs, Redis Streams is acceptable, but must be upgraded before physical pilots.
